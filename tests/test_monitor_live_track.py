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


def test_execution_freshness_labels_reconcile_runs_as_runs_not_trades(
    tmp_path: Path,
) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "last_key": "SPEC|2026-10-30|2026-10-31",
                "last_status": "ok",
                "last_run_at": "2026-10-31T03:06:16+00:00",
            }
        ),
        encoding="utf-8",
    )

    fresh, detail = _execution_freshness(
        state_file,
        datetime(2026, 10, 31, 5, 0, tzinfo=timezone.utc),
    )

    assert fresh is True
    assert "最近成功运行" in detail
    assert "最近成功执行" not in detail


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

    assert command[command.index("--capital-flows-file") + 1] == str(flows)


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


def test_monitor_defaults_belong_to_the_ls45_live_book() -> None:
    from scripts import monitor_live_track

    assert monitor_live_track.DEFAULT_STATE_FILE == Path(
        "data/ls45_g125_execution_state.json"
    )
    assert monitor_live_track.DEFAULT_OUT == Path(
        "reports/ls45_live_g125_live/health.json"
    )


def test_monitor_compares_signed_short_notional_to_the_signed_target() -> None:
    import pytest
    from scripts import monitor_live_track

    positions = [
        {"symbol": "NEARUSDT", "total": "20", "posSide": "short", "markPrice": "5"},
        {"symbol": "TRXUSDT", "total": "-10", "posSide": "net", "markPrice": "2"},
    ]

    actual = monitor_live_track._position_notional(
        positions,
        {"near": "NEARUSDT", "tron": "TRXUSDT"},
    )

    assert actual["near"] == pytest.approx(-100.0)
    assert actual["tron"] == pytest.approx(-20.0)


def test_audit_timeout_becomes_a_diagnostic_instead_of_an_unhandled_exception(tmp_path, monkeypatch) -> None:
    import subprocess
    from scripts import monitor_live_track

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="audit", timeout=180)

    monkeypatch.setattr(monitor_live_track.subprocess, "run", timeout)

    code, payload, stderr = monitor_live_track._run_audit(tmp_path / "flows.csv")

    assert code == 124
    assert payload == {}
    assert "timed out" in stderr


def test_monitor_can_persist_the_audit_payload_for_operators(tmp_path, monkeypatch) -> None:
    import subprocess
    from scripts import monitor_live_track

    audit_out = tmp_path / "audit.json"

    def fake_run(command, *, cwd, capture_output, text, timeout):
        assert "--json-out" in command
        json_path = Path(command[command.index("--json-out") + 1])
        json_path.write_text(
            json.dumps({"hard_failures": 0, "equity": 500.0}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(monitor_live_track.subprocess, "run", fake_run)

    code, payload, stderr = monitor_live_track._run_audit(
        tmp_path / "flows.csv",
        audit_out=audit_out,
    )

    assert code == 0
    assert payload["equity"] == 500.0
    assert stderr == ""
    assert audit_out.exists()


def test_monitor_unexpected_failure_is_written_and_notified(tmp_path, monkeypatch) -> None:
    from scripts import monitor_live_track

    monkeypatch.setenv("ATLAS20_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "123")
    sent: list[str] = []

    def fail(*args, **kwargs):
        raise RuntimeError("venue unavailable")

    def capture(message, **kwargs):
        sent.append(message)

    monkeypatch.setattr(monitor_live_track, "_run_audit", fail)
    monkeypatch.setattr(monitor_live_track, "send_telegram_message", capture)
    out = tmp_path / "health.json"

    code = monitor_live_track.main(["--notify", "--quiet", "--out", str(out)])

    assert code == 1
    assert sent and "venue unavailable" in sent[0]
    assert json.loads(out.read_text(encoding="utf-8"))["issues"]


def test_audit_command_carries_the_ls104_paths_and_spec(tmp_path: Path) -> None:
    from scripts import monitor_live_track
    from atlas20.derivatives.live_chain import LS104_G175_M090_SPEC

    command = monitor_live_track._audit_command(
        tmp_path / "audit.json",
        tmp_path / "flows.csv",
        spec=LS104_G175_M090_SPEC,
        targets_file=Path("reports/ls45_live_g175/oos_targets.csv"),
        manifest_file=Path("reports/ls45_live_g175/manifest.json"),
        state_file=Path("data/ls45_g175_execution_state.json"),
        journal_file=Path("reports/ls45_live_g175_live/journal.csv"),
    )

    assert command[command.index("--spec") + 1] == LS104_G175_M090_SPEC
    assert command[command.index("--targets-file") + 1] == "reports/ls45_live_g175/oos_targets.csv"
    assert command[command.index("--manifest-file") + 1] == "reports/ls45_live_g175/manifest.json"
    assert command[command.index("--state-file") + 1] == "data/ls45_g175_execution_state.json"
    assert command[command.index("--journal-file") + 1] == "reports/ls45_live_g175_live/journal.csv"
