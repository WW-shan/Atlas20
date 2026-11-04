from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import pytest

from atlas20.derivatives.live_executor import ExecutionReport
from atlas20.derivatives.live_journal import JournalEntry
from scripts import execute_live_plan


def test_state_is_not_marked_complete_when_journal_write_fails(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.csv"
    journal_path.mkdir()
    state_path = tmp_path / "state.json"
    entry = JournalEntry(
        date="2026-10-31",
        run_at_utc="2026-10-31T03:06:16+00:00",
        signal_date="2026-10-30",
        equity=100.0,
        position_value=0.0,
        cash=100.0,
        day_pnl=0.0,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
    )

    persist = getattr(execute_live_plan, "_persist_run_result")
    with pytest.raises(OSError):
        persist(
            json_out=tmp_path / "latest.json",
            payload={"status": "ok"},
            journal_file=journal_path,
            entry=entry,
            state_file=state_path,
            key="SPEC|2026-10-30|2026-10-31",
            status="ok",
            report=ExecutionReport(signal_date="2026-10-30"),
        )

    assert not state_path.exists()


def test_state_is_not_marked_complete_when_notification_fails(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    entry = JournalEntry(
        date="2026-10-31",
        run_at_utc="2026-10-31T03:06:16+00:00",
        signal_date="2026-10-30",
        equity=100.0,
        position_value=0.0,
        cash=100.0,
        day_pnl=0.0,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
    )

    def fail_notification() -> None:
        raise RuntimeError("telegram unavailable")

    persist = getattr(execute_live_plan, "_persist_run_result")
    with pytest.raises(RuntimeError, match="telegram unavailable"):
        persist(
            json_out=tmp_path / "latest.json",
            payload={"status": "ok"},
            journal_file=tmp_path / "journal.csv",
            entry=entry,
            state_file=state_path,
            key="SPEC|2026-10-30|2026-10-31",
            status="ok",
            report=ExecutionReport(signal_date="2026-10-30"),
            notify=fail_notification,
        )

    assert not state_path.exists()


def test_external_deposit_is_excluded_from_daily_pnl() -> None:
    report = ExecutionReport(
        signal_date="2026-11-03",
        equity_before=501.0,
        equity_after=501.0,
        balance_after=501.0,
    )

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-03",
        run_at=datetime(2026, 11, 4, 11, 15, tzinfo=timezone.utc),
        prev_equity=100.0,
        capital_flow=400.0,
        warnings=[],
    )

    assert entry.day_pnl == pytest.approx(1.0)
    assert entry.day_return == pytest.approx(0.002)
    assert entry.capital_flow == pytest.approx(400.0)
