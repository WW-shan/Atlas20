from __future__ import annotations

from pathlib import Path

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
