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
    assert _scheduled_utc_times() == [(2, 30), (6, 30)]


def test_refresh_runs_after_the_utc_close_is_published():
    for hour, _minute in _scheduled_utc_times():
        assert 1 <= hour < 8, "a run before 00:00 UTC cannot see the last completed day's close"
