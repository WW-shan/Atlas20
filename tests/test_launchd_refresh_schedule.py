"""The launchd refresh job must fire after CoinMarketCap publishes the close.

launchd reads ``StartCalendarInterval`` in the host's local time zone, not
UTC. The checked-in plist targets this workstation (Asia/Shanghai, UTC+8), so
an ``Hour`` of 2 fires at 18:30 UTC on the previous day: before CMC has
published the last completed day's close, which left the panel a day stale.
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


def test_refresh_runs_at_documented_utc_times():
    assert _scheduled_utc_times() == [(2, 30), (2, 55), (6, 30)]


def test_a_catchup_lands_before_the_trade_job_reads_the_panel():
    """A primary run killed by a reboot must be repaired before 03:05 UTC.

    On 2026-10-16 the machine went down mid-refresh at 10:34 Beijing, the panel
    stayed on 10-14, and the 11:05 trade job failed closed with nothing to
    trade. The 10:55 catch-up is the fix; the trade job also self-heals.
    """

    execute_plist = PLIST_PATH.parent / "com.atlas20.derivatives-execute.plist"
    trade_hour, trade_minute = _trade_utc_time(execute_plist)

    assert any(
        (hour, minute) > (2, 30) and (hour, minute) < (trade_hour, trade_minute)
        for hour, minute in _scheduled_utc_times()
    ), "a catch-up must fire between the primary refresh and the trade job"


def test_refresh_runs_after_the_utc_close_is_published():
    for hour, _minute in _scheduled_utc_times():
        assert 1 <= hour < 8, "a run before 00:00 UTC cannot see the last completed day's close"

def _trade_utc_time(plist_path: Path) -> tuple[int, int]:
    payload = plistlib.loads(plist_path.read_bytes())
    entry = payload["StartCalendarInterval"]
    local = datetime(2026, 1, 15, entry["Hour"], entry["Minute"], tzinfo=PLIST_LOCAL_ZONE)
    utc = local.astimezone(timezone.utc)
    return (utc.hour, utc.minute)

def test_refresh_job_runs_through_the_locked_wrapper() -> None:
    """Every fire must go through the lock and the freshness skip.

    The plist used to chain download and build with ``&&``; that cannot take a
    lock, so the pre-trade catch-up could race a slow primary run into the
    same raw cache.
    """

    payload = plistlib.loads(PLIST_PATH.read_bytes())
    command = payload["ProgramArguments"][-1]

    assert "scripts/refresh_daily_data.py" in command
    assert "download_data.py" not in command
    assert payload["RunAtLoad"] is False
