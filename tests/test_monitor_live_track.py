from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from atlas20.derivatives.live_journal import (
    JournalEntry,
    append_capital_flow,
    load_journal,
    upsert_entry,
)
from scripts.monitor_live_track import (
    _audit_command,
    _audit_failure_details,
    _audit_metrics,
    _execution_freshness,
    _gross_ratio,
    _ledger_change,
)


def test_execution_freshness_rejects_a_partial_last_run(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "last_key": "SPEC|2026-10-30|2026-10-31",
                "last_status": "partial",
                "last_run_at": "2026-10-31T03:06:16+00:00",
            }
        ),
        encoding="utf-8",
    )

    fresh, detail = _execution_freshness(
        state_file,
        datetime(2026, 10, 31, 5, 0, tzinfo=timezone.utc),
    )

    assert fresh is False
    assert "partial" in detail


def test_ledger_change_excludes_a_deposit_made_after_the_last_row(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.csv"
    flows_path = tmp_path / "capital_flows.csv"
    upsert_entry(
        journal_path,
        JournalEntry(
            date="2026-11-04",
            run_at_utc="2026-11-04T03:06:00+00:00",
            signal_date="2026-11-03",
            equity=99.68,
            position_value=0.0,
            cash=99.68,
            day_pnl=0.0,
            day_return=0.0,
            fees_today=0.0,
            funding_total=0.0,
            unrealised_pnl=0.0,
        ),
    )
    append_capital_flow(
        flows_path,
        timestamp_utc="2026-11-04T11:15:00+00:00",
        amount_usdt=400.0,
        note="deposit",
    )

    change = _ledger_change(
        load_journal(journal_path),
        flows_path,
        equity=499.68,
        now=datetime(2026, 11, 4, 11, 30, tzinfo=timezone.utc),
    )

    assert change == 0.0


def test_audit_subprocess_uses_the_configured_capital_flows_file(tmp_path: Path) -> None:
    json_out = tmp_path / "audit.json"
    flows = tmp_path / "capital_flows.csv"

    command = _audit_command(json_out, flows)

    assert command[-2:] == ["--capital-flows-file", str(flows)]


def test_alert_names_the_failed_audit_check() -> None:
    detail = _audit_failure_details(
        {
            "hard_failures": 1,
            "checks": [
                {"check": "台账最新一行 = 当前账户", "ok": False, "hard": True, "detail": "差 400"},
                {"check": "mark 数据新鲜", "ok": True, "hard": True, "detail": "1.1h"},
            ],
        }
    )

    assert "台账最新一行 = 当前账户" in detail
    assert "差 400" in detail
    assert "mark 数据新鲜" not in detail


def test_missing_audit_payload_never_becomes_zero_equity() -> None:
    assert _audit_metrics({}) == (None, None)
    assert _audit_metrics({"equity": "499.68", "position_value": 0}) == (499.68, 0.0)


def test_audit_process_failure_reports_its_exit_code_and_stderr() -> None:
    detail = _audit_failure_details(
        {},
        exit_code=1,
        stderr="requests.exceptions.SSLError: EOF occurred in violation of protocol",
    )

    assert "退出码 1" in detail
    assert "SSLError" in detail


def test_gross_ratio_is_unknown_when_equity_is_zero() -> None:
    assert _gross_ratio(gross=0.0, equity=0.0) is None
    assert _gross_ratio(gross=25.0, equity=100.0) == 0.25
