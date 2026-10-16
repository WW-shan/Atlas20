"""Preflight gates that keep the daily live chain honest.

Two failure modes motivated these helpers:

* a shutdown or reboot in the middle of the 10:30 panel refresh leaves
  ``data/processed/panel_daily.csv`` a day behind while the Bitget mark tree
  keeps moving, so the executor's freshness guard fails closed and the day's
  rebalance is silently skipped (this happened on 2026-10-16);
* the machine may be off at the scheduled fire time, so the day's rebalance
  is never attempted at all.

The gates answer "is the panel current?" and "should the chain run at all
right now?" so the wrapper can self-heal the first and catch up the second.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path

import pandas as pd
import pytest

from atlas20.derivatives.live_chain import (
    DEFAULT_CATCHUP_HOURS,
    DEFAULT_SCHEDULED_UTC,
    last_completed_utc_day,
    panel_end_date,
    panel_lags_last_completed_day,
    run_day_already_done,
    within_run_window,
)

NOW = datetime(2026, 10, 16, 3, 5, tzinfo=timezone.utc)


def _write_panel(path: Path, days: list[str]) -> Path:
    pd.DataFrame(
        {"date": days, "coin_id": [f"coin-{index}" for index in range(len(days))]}
    ).to_csv(path, index=False)
    return path


def _write_state(path: Path, key: str, status: str) -> Path:
    path.write_text(json.dumps({"last_key": key, "last_status": status}), encoding="utf-8")
    return path


def test_last_completed_utc_day_is_yesterday() -> None:
    assert last_completed_utc_day(NOW) == date(2026, 10, 15)


def test_last_completed_utc_day_ignores_a_still_forming_bar() -> None:
    # 2026-10-15 23:00 UTC: the 10-15 bar has not closed yet, so the newest
    # day a signal may use is 10-14.
    assert last_completed_utc_day(datetime(2026, 10, 15, 23, 0, tzinfo=timezone.utc)) == date(
        2026, 10, 14
    )


def test_panel_end_date_reads_the_newest_row(tmp_path: Path) -> None:
    panel = _write_panel(tmp_path / "panel_daily.csv", ["2026-10-13", "2026-10-15", "2026-10-14"])
    assert panel_end_date(panel) == date(2026, 10, 15)


def test_panel_end_date_is_none_when_the_panel_is_missing(tmp_path: Path) -> None:
    assert panel_end_date(tmp_path / "absent.csv") is None


def test_panel_that_stops_at_the_previous_day_lags(tmp_path: Path) -> None:
    panel = _write_panel(tmp_path / "panel_daily.csv", ["2026-10-13", "2026-10-14"])
    assert panel_lags_last_completed_day(panel, NOW) is True


def test_panel_that_carries_the_last_completed_day_is_current(tmp_path: Path) -> None:
    panel = _write_panel(tmp_path / "panel_daily.csv", ["2026-10-14", "2026-10-15"])
    assert panel_lags_last_completed_day(panel, NOW) is False


def test_missing_panel_counts_as_lagging(tmp_path: Path) -> None:
    assert panel_lags_last_completed_day(tmp_path / "absent.csv", NOW) is True


def test_run_day_already_done_matches_the_executor_state_key(tmp_path: Path) -> None:
    state = _write_state(
        tmp_path / "state.json",
        "PR2026-10-D-L125-V2|2026-10-14|2026-10-16",
        "ok",
    )
    assert run_day_already_done(state, date(2026, 10, 16)) is True
    assert run_day_already_done(state, date(2026, 10, 17)) is False


def test_run_day_already_done_is_false_after_a_failed_run(tmp_path: Path) -> None:
    state = _write_state(
        tmp_path / "state.json",
        "PR2026-10-D-L125-V2|2026-10-14|2026-10-16",
        "failed",
    )
    assert run_day_already_done(state, date(2026, 10, 16)) is False


def test_run_day_already_done_is_false_without_a_state_file(tmp_path: Path) -> None:
    assert run_day_already_done(tmp_path / "absent.json", date(2026, 10, 16)) is False


def test_run_day_already_done_ignores_a_key_without_a_run_day(tmp_path: Path) -> None:
    state = _write_state(tmp_path / "state.json", "PR2026-10-D-L125-V2|2026-10-14", "ok")
    assert run_day_already_done(state, date(2026, 10, 16)) is False


def test_window_opens_at_the_fill_time() -> None:
    before = datetime(2026, 10, 16, 3, 4, tzinfo=timezone.utc)
    ok, reason = within_run_window(before)
    assert ok is False
    assert "before" in reason

    ok, _ = within_run_window(datetime(2026, 10, 16, 3, 5, tzinfo=timezone.utc))
    assert ok is True


def test_window_closes_after_the_catchup_budget() -> None:
    inside = NOW + timedelta(hours=DEFAULT_CATCHUP_HOURS - 0.01)
    assert within_run_window(inside)[0] is True

    outside = NOW + timedelta(hours=DEFAULT_CATCHUP_HOURS + 0.01)
    ok, reason = within_run_window(outside)
    assert ok is False
    assert "catch-up" in reason


def test_window_honours_a_shifted_schedule() -> None:
    moment = datetime(2026, 10, 16, 3, 30, tzinfo=timezone.utc)
    assert within_run_window(moment, scheduled_utc=time(4, 0))[0] is False
    assert within_run_window(moment, scheduled_utc=time(3, 0))[0] is True


@pytest.mark.parametrize(
    ("hour", "minute"),
    [(DEFAULT_SCHEDULED_UTC.hour, DEFAULT_SCHEDULED_UTC.minute)],
)
def test_default_schedule_matches_the_launchd_job(hour: int, minute: int) -> None:
    # ops/com.atlas20.derivatives-execute.plist fires at 11:05 Beijing = 03:05
    # UTC; the gate must not open before the model's T+1 fill point.
    assert (hour, minute) == (3, 5)
