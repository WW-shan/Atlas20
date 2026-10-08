"""The launchd CMC probe must fire inside the daily publication window.

launchd reads ``StartCalendarInterval`` in the host's local time zone, not UTC.
The checked-in plist targets this workstation (Asia/Shanghai, UTC+8), so the
conversion has to hold: the probe is only informative between about 00:05 and
03:05 UTC, the window in which CoinMarketCap finishes writing day D-1.
"""

from __future__ import annotations

from datetime import datetime, timezone
import plistlib
from pathlib import Path
from zoneinfo import ZoneInfo

PLIST_PATH = Path(__file__).resolve().parents[1] / "ops" / "com.atlas20.cmc-probe.plist"
PLIST_LOCAL_ZONE = ZoneInfo("Asia/Shanghai")
# The measurement window, in UTC. Anything outside it cannot move the decision.
WINDOW_START_UTC = (0, 5)
WINDOW_END_UTC = (3, 50)


def _scheduled_utc_times() -> list[tuple[int, int]]:
    payload = plistlib.loads(PLIST_PATH.read_bytes())
    times: list[tuple[int, int]] = []
    for entry in payload["StartCalendarInterval"]:
        local = datetime(2026, 1, 15, entry["Hour"], entry["Minute"], tzinfo=PLIST_LOCAL_ZONE)
        utc = local.astimezone(timezone.utc)
        times.append((utc.hour, utc.minute))
    return sorted(times)


def test_probe_runs_on_the_documented_utc_grid():
    times = _scheduled_utc_times()
    assert times == [(hour, minute) for hour in (0, 1, 2, 3) for minute in (5, 20, 35, 50)]


def test_probe_stays_inside_the_publication_window():
    for moment in _scheduled_utc_times():
        assert WINDOW_START_UTC <= moment <= WINDOW_END_UTC


def test_probe_is_not_run_at_load():
    payload = plistlib.loads(PLIST_PATH.read_bytes())
    # A load-time run would fire outside the window and pollute the series.
    assert payload["RunAtLoad"] is False
