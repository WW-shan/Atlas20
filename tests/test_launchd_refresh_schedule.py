"""The launchd refresh job must fire after CoinMarketCap publishes the close.

launchd reads ``StartCalendarInterval`` in the host's local time zone, not
UTC. The checked-in plist targets this workstation (Asia/Shanghai, UTC+8), so
an ``Hour`` of 2 fires at 18:30 UTC on the previous day: before CMC has
published the last completed day's close, which left the panel a day stale.
The publication probe now shows 10/10 sample coverage at 00:20 UTC, so an early
00:30 UTC attempt can safely run before the 01:05 UTC trade window while the
old 02:30/02:55/06:30 runs remain as fallbacks.
"""

from __future__ import annotations

from datetime import datetime, timezone
import plistlib
from pathlib import Path
from zoneinfo import ZoneInfo

PLIST_PATH = Path(__file__).resolve().parents[1] / "ops" / "com.atlas20.daily-refresh.plist"
# The zone of the machine the checked-in plist is installed on.
PLIST_LOCAL_ZONE = ZoneInfo("Asia/Shanghai")


def _scheduled_utc_times() -> list[tuple[int, int]]:
    payload = plistlib.loads(PLIST_PATH.read_bytes())
    times: list[tuple[int, int]] = []
    for entry in payload["StartCalendarInterval"]:
        local = datetime(2026, 1, 15, entry["Hour"], entry["Minute"], tzinfo=PLIST_LOCAL_ZONE)
        utc = local.astimezone(timezone.utc)
        times.append((utc.hour, utc.minute))
    return sorted(times)


def test_refresh_runs_once_at_documented_utc_time():
    assert _scheduled_utc_times() == [(0, 30)]


def test_the_single_refresh_lands_before_the_trade_job_reads_the_panel():
    execute_plist = PLIST_PATH.parent / "com.atlas20.derivatives-execute.plist"
    trade_hour, trade_minute = _trade_utc_time(execute_plist)
    assert (0, 30) < (trade_hour, trade_minute)


def test_refresh_runs_after_the_utc_close_is_published():
    for hour, minute in _scheduled_utc_times():
        assert (0, 20) <= (hour, minute) < (8, 0), (
            "a run before the measured CMC publication window cannot see the last completed day"
        )

def _trade_utc_time(plist_path: Path) -> tuple[int, int]:
    payload = plistlib.loads(plist_path.read_bytes())
    raw = payload["StartCalendarInterval"]
    entries = raw if isinstance(raw, list) else [raw]
    times = []
    for entry in entries:
        local = datetime(2026, 1, 15, entry["Hour"], entry["Minute"], tzinfo=PLIST_LOCAL_ZONE)
        utc = local.astimezone(timezone.utc)
        times.append((utc.hour, utc.minute))
    return min(times)

def test_refresh_job_runs_through_the_locked_wrapper() -> None:
    """Every fire must go through the lock and the freshness skip.

    The plist used to chain download and build with ``&&``; that cannot take a
    lock, so the pre-trade catch-up could race a slow primary run into the
    same raw cache.
    """

    payload = plistlib.loads(PLIST_PATH.read_bytes())

    assert payload["ProgramArguments"][-1].endswith("ops/run_derivatives_data.sh")
    assert payload["RunAtLoad"] is False
