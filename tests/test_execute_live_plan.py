from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json

import pytest
import pandas as pd

from atlas20.derivatives.execution import ExecutionPlan, MarginIntent, OrderIntent
from atlas20.derivatives.live_executor import ExecutionReport, OrderFill
from atlas20.derivatives.live_journal import JournalEntry
from scripts import execute_live_plan
from scripts.plan_live_execution import account_state_from_bitget


class _QuoteResponse:
    ok = True
    status_code = 200

    def json(self):
        return {
            "code": "00000",
            "msg": "success",
            "requestTime": 1_800_000_000_000,
            "data": [
                {
                    "symbol": "BTCUSDT",
                    "ts": "1799999999000",
                    "lastPrice": "100.0",
                    "markPrice": "100.1",
                    "bid1Price": "99.9",
                    "ask1Price": "100.2",
                    "bid1Size": "3.0",
                    "ask1Size": "2.0",
                }
            ],
        }


class _QuoteSession:
    def get(self, url, params, timeout):
        return _QuoteResponse()


class _PositionClient:
    def account_assets(self):
        return {"usdtEquity": "100", "assets": [{"coin": "USDT", "available": "100"}]}

    def current_positions(self):
        return [{"symbol": "TRXUSDT", "total": "1", "posSide": "long"}]


def test_live_quote_snapshot_returns_prices_and_execution_warnings() -> None:
    prices, quotes, warnings = execute_live_plan._live_quote_snapshot(
        _QuoteSession(),  # type: ignore[arg-type]
        {"BTCUSDT"},
        max_age_seconds=120.0,
        spread_warning_bps=20.0,
        mark_deviation_warning_bps=5.0,
    )

    assert prices == {"BTCUSDT": pytest.approx(100.0)}
    assert quotes["BTCUSDT"].mark_price == pytest.approx(100.1)
    assert any("BTCUSDT" in warning for warning in warnings)


def _valid_manifest_payload(**overrides):
    from atlas20.derivatives.live_chain import (
        LS45_G125_FROZEN_CONFIG,
        LS45_G125_MANIFEST_TOP_LEVEL,
        LS45_G125_SPEC,
    )

    payload = {
        "tracked_spec": LS45_G125_SPEC,
        "frozen_config": LS45_G125_FROZEN_CONFIG,
        **LS45_G125_MANIFEST_TOP_LEVEL,
    }
    payload.update(overrides)
    return payload


def _manifest_args(**overrides):
    import argparse

    values = {
        "spec": "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21",
        "max_gross_multiple": 1.25,
        "long_buffer": 0.50,
        "short_buffer": 0.50,
        "short_stop_loss_pct": 0.20,
        "cost_bps": 20.0,
        "leverage": 2.0,
        "max_margin_utilization": 0.85,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_live_manifest_matches_the_pinned_ls45_spec() -> None:
    from atlas20.derivatives.live_chain import (
        LS45_G125_FROZEN_CONFIG,
        LS45_G125_MANIFEST_TOP_LEVEL,
        LS45_G125_SPEC,
    )

    manifest = {
        "tracked_spec": LS45_G125_SPEC,
        "frozen_config": LS45_G125_FROZEN_CONFIG,
        **LS45_G125_MANIFEST_TOP_LEVEL,
    }

    assert execute_live_plan._manifest_spec_issues(manifest, _manifest_args()) == []


def test_live_manifest_rejects_a_changed_profit_lock_horizon() -> None:
    from atlas20.derivatives.live_chain import (
        LS45_G125_FROZEN_CONFIG,
        LS45_G125_MANIFEST_TOP_LEVEL,
        LS45_G125_SPEC,
    )

    config = {
        **LS45_G125_FROZEN_CONFIG,
        "profit_lock_redistribution": {
            **LS45_G125_FROZEN_CONFIG["profit_lock_redistribution"],
            "recipient_confirmation_days": 7,
        },
    }
    manifest = {
        "tracked_spec": LS45_G125_SPEC,
        "frozen_config": config,
        **LS45_G125_MANIFEST_TOP_LEVEL,
    }

    issues = execute_live_plan._manifest_spec_issues(manifest, _manifest_args())

    assert any("profit_lock_redistribution" in issue for issue in issues)


def test_live_manifest_rejects_a_non_isolated_venue_leverage() -> None:
    from atlas20.derivatives.live_chain import (
        LS45_G125_FROZEN_CONFIG,
        LS45_G125_MANIFEST_TOP_LEVEL,
        LS45_G125_SPEC,
    )

    manifest = {
        "tracked_spec": LS45_G125_SPEC,
        "frozen_config": LS45_G125_FROZEN_CONFIG,
        **LS45_G125_MANIFEST_TOP_LEVEL,
    }

    issues = execute_live_plan._manifest_spec_issues(
        manifest, _manifest_args(leverage=3.0)
    )

    assert any("leverage=3" in issue for issue in issues)


def test_live_manifest_rejects_a_second_execution_clock() -> None:
    manifest = _valid_manifest_payload(execution_utc="03:00")

    issues = execute_live_plan._manifest_spec_issues(manifest, _manifest_args())

    assert any("execution_utc" in issue for issue in issues)


def test_live_execution_rejects_a_data_fingerprint_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    from atlas20.derivatives.data_audit import DataAuditReport
    from atlas20.derivatives.live_chain import file_sha256

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            _valid_manifest_payload(
                signal_end_date="2026-11-13",
                index_end_date="2026-11-13",
                last_mark="2026-11-14T00:00:00+00:00",
                data_fingerprint="sha256:manifest",
                data_audit_passed=True,
                targets_file=execute_live_plan.DEFAULT_TARGETS_FILE.name,
                targets_sha256=file_sha256(execute_live_plan.DEFAULT_TARGETS_FILE),
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        execute_live_plan,
        "audit_derivatives_data",
        lambda *args, **kwargs: DataAuditReport(
            passed=True,
            provenance={"fingerprint": "sha256:current"},
        ),
    )

    args = execute_live_plan.parse_args(
        ["--live", "--manifest-file", str(manifest), "--force"]
    )
    with pytest.raises(SystemExit, match="data_fingerprint"):
        execute_live_plan._main(args)


def test_unmapped_live_position_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="not in the frozen symbol map"):
        account_state_from_bitget(_PositionClient(), {"near": "NEARUSDT"})  # type: ignore[arg-type]


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


def test_persisted_state_records_the_bitget_account_fingerprint(tmp_path: Path) -> None:
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
    state_path = tmp_path / "state.json"

    execute_live_plan._persist_run_result(
        json_out=tmp_path / "latest.json",
        payload={"status": "ok"},
        journal_file=tmp_path / "journal.csv",
        entry=entry,
        state_file=state_path,
        key="SPEC|2026-10-30|2026-10-31",
        status="ok",
        report=ExecutionReport(signal_date="2026-10-30"),
        account_fp="account-fingerprint",
    )

    assert json.loads(state_path.read_text(encoding="utf-8"))["account_fingerprint"] == "account-fingerprint"


def test_same_day_retry_preserves_the_earlier_filled_trade(tmp_path: Path) -> None:
    from atlas20.derivatives.live_journal import load_journal

    journal_path = tmp_path / "journal.csv"
    state_path = tmp_path / "state.json"
    base = {
        "date": "2026-10-31",
        "run_at_utc": "2026-10-31T03:06:16+00:00",
        "signal_date": "2026-10-30",
        "equity": 100.0,
        "position_value": 0.0,
        "cash": 100.0,
        "day_pnl": 0.0,
        "day_return": 0.0,
        "funding_total": 0.0,
        "unrealised_pnl": 0.0,
    }
    first = JournalEntry(
        **base,
        fees_today=0.06,
        trades=[
            {
                "order_id": "order-1",
                "symbol": "NEARUSDT",
                "action": "OPEN",
                "qty": 10.0,
                "fee": 0.06,
                "status": "filled",
            }
        ],
        notes=["first attempt"],
    )
    second = JournalEntry(
        **{**base, "run_at_utc": "2026-10-31T04:06:16+00:00"},
        fees_today=0.0,
        trades=[],
        notes=["retry completed"],
    )

    persist = execute_live_plan._persist_run_result
    persist(
        json_out=tmp_path / "latest.json",
        payload={"status": "partial"},
        journal_file=journal_path,
        entry=first,
        state_file=state_path,
        key="SPEC|2026-10-30|2026-10-31",
        status="partial",
        report=ExecutionReport(signal_date="2026-10-30"),
    )
    persist(
        json_out=tmp_path / "latest.json",
        payload={"status": "ok"},
        journal_file=journal_path,
        entry=second,
        state_file=state_path,
        key="SPEC|2026-10-30|2026-10-31",
        status="ok",
        report=ExecutionReport(signal_date="2026-10-30"),
    )

    row = load_journal(journal_path).iloc[0]
    assert json.loads(row["trades"])[0]["order_id"] == "order-1"
    assert row["fees_today"] == pytest.approx(0.06)
    assert json.loads(row["notes"]) == ["first attempt", "retry completed"]


def test_same_day_retry_carries_prior_flow_and_adds_only_new_flow(tmp_path: Path) -> None:
    from atlas20.derivatives.live_journal import append_capital_flow, load_journal, upsert_entry

    journal_path = tmp_path / "journal.csv"
    flow_path = tmp_path / "capital_flows.csv"
    append_capital_flow(
        flow_path,
        timestamp_utc="2026-11-04T10:00:00+00:00",
        amount_usdt=400.0,
        note="deposit",
    )
    upsert_entry(
        journal_path,
        JournalEntry(
            date="2026-11-04",
            run_at_utc="2026-11-04T11:00:00+00:00",
            signal_date="2026-11-03",
            equity=500.0,
            position_value=0.0,
            cash=500.0,
            day_pnl=None,
            day_return=None,
            fees_today=0.0,
            funding_total=0.0,
            unrealised_pnl=0.0,
            capital_flow=400.0,
            notes=["外部资金流 +400.00 USDT（已从盈亏中剔除）"],
        ),
    )
    append_capital_flow(
        flow_path,
        timestamp_utc="2026-11-04T12:00:00+00:00",
        amount_usdt=25.0,
        note="deposit",
    )

    journal = load_journal(journal_path)
    flow = execute_live_plan._capital_flow_for_run(
        journal,
        flow_path,
        run_at=datetime(2026, 11, 4, 13, 0, tzinfo=timezone.utc),
    )

    assert flow == pytest.approx(425.0)


def test_same_day_retry_replaces_stale_capital_flow_note() -> None:
    previous = JournalEntry(
        date="2026-11-04",
        run_at_utc="2026-11-04T11:00:00+00:00",
        signal_date="2026-11-03",
        equity=500.0,
        position_value=0.0,
        cash=500.0,
        day_pnl=None,
        day_return=None,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        capital_flow=400.0,
        notes=["外部资金流 +400.00 USDT（已从盈亏中剔除）", "first attempt"],
    )
    current = JournalEntry(
        date="2026-11-04",
        run_at_utc="2026-11-04T13:00:00+00:00",
        signal_date="2026-11-03",
        equity=525.0,
        position_value=0.0,
        cash=525.0,
        day_pnl=None,
        day_return=None,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        capital_flow=425.0,
        notes=["外部资金流 +425.00 USDT（已从盈亏中剔除）", "retry"],
    )

    merged = execute_live_plan._merge_same_day_entry(previous.as_row(), current)

    assert merged.notes == [
        "first attempt",
        "外部资金流 +425.00 USDT（已从盈亏中剔除）",
        "retry",
    ]


def test_same_day_retry_replaces_a_stale_signal_age_note() -> None:
    previous = JournalEntry(
        date="2026-11-14",
        run_at_utc="2026-11-14T01:11:48+00:00",
        signal_date="2026-11-06",
        equity=499.6,
        position_value=0.0,
        cash=499.6,
        day_pnl=None,
        day_return=None,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        capital_flow=0.0,
        notes=[
            "最新信号事件在 8 天前（事件驱动策略，无变化＝继续持有；"
            "若与回测不一致请跑 make audit-live）",
            "stable context",
        ],
    )
    current = JournalEntry(
        date="2026-11-14",
        run_at_utc="2026-11-14T14:14:40+00:00",
        signal_date="2026-11-13",
        equity=499.6,
        position_value=120.0,
        cash=379.6,
        day_pnl=None,
        day_return=None,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        capital_flow=0.0,
        notes=["retry with the current signal"],
    )

    merged = execute_live_plan._merge_same_day_entry(previous.as_row(), current)

    assert merged.notes == ["stable context", "retry with the current signal"]


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


class _OneWayShortClient:
    def account_assets(self):
        return {"usdtEquity": "100", "assets": [{"coin": "USDT", "available": "100"}]}

    def current_positions(self):
        return [
            {
                "symbol": "NEARUSDT",
                "total": "-2",
                "posSide": "net",
                "avgPrice": "5",
                "markPrice": "5",
                "positionBalance": "5",
            }
        ]


def test_one_way_negative_position_is_recorded_as_short() -> None:
    account = account_state_from_bitget(
        _OneWayShortClient(),  # type: ignore[arg-type]
        {"near": "NEARUSDT"},
    )

    assert account.positions["near"].side == "short"
    assert account.positions["near"].size == pytest.approx(2.0)


def test_journal_records_a_one_way_negative_position_as_a_signed_short() -> None:
    report = ExecutionReport(
        signal_date="2026-11-13",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {
                "asset": "near",
                "symbol": "NEARUSDT",
                "total": "-20",
                "posSide": "net",
                "avgPrice": "5",
                "markPrice": "5",
            }
        ],
    )

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-13",
        run_at=datetime(2026, 11, 14, 3, 5, tzinfo=timezone.utc),
        prev_equity=None,
        capital_flow=0.0,
        warnings=[],
    )

    assert entry.positions[0]["side"] == "short"
    assert entry.positions[0]["qty"] == pytest.approx(20.0)
    assert entry.positions[0]["weight"] == pytest.approx(-1.0)


def test_journal_records_the_normalized_stop_used_by_the_live_position() -> None:
    report = ExecutionReport(
        signal_date="2026-11-13",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {
                "asset": "near",
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "avgPrice": "5.5",
                "markPrice": "5.5",
            }
        ],
        normalized_short_stops={"NEARUSDT": 6.6},
    )

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-13",
        run_at=datetime(2026, 11, 14, 3, 5, tzinfo=timezone.utc),
        prev_equity=None,
        capital_flow=0.0,
        warnings=[],
    )

    assert entry.positions[0]["normalized_stop_loss"] == pytest.approx(6.6)


def test_journal_funding_total_is_a_delta_not_a_cumulative_snapshot() -> None:
    report = ExecutionReport(
        signal_date="2026-11-03",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {
                "asset": "near",
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "long",
                "avgPrice": "5",
                "markPrice": "5",
                "totalFunding": "-0.13",
            }
        ],
    )
    previous = {
        "positions": json.dumps(
            [
                {
                    "symbol": "NEARUSDT",
                    "side": "long",
                    "qty": 20.0,
                    "funding_cumulative": -0.10,
                }
            ]
        )
    }

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-03",
        run_at=datetime(2026, 11, 4, 3, 5, tzinfo=timezone.utc),
        prev_equity=100.0,
        capital_flow=0.0,
        warnings=[],
        previous=previous,
    )

    assert entry.funding_total == pytest.approx(-0.03)
    assert entry.positions[0]["funding_cumulative"] == pytest.approx(-0.13)


def test_journal_counts_the_full_funding_of_a_new_position_cycle() -> None:
    report = ExecutionReport(
        signal_date="2026-11-03",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {
                "asset": "near",
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "avgPrice": "5",
                "markPrice": "5",
                "totalFunding": "-0.08",
            }
        ],
        fills=[
            OrderFill(
                asset="near",
                symbol="NEARUSDT",
                action="OPEN",
                side="sell",
                stop_loss=6.0,
                requested_size=20.0,
                filled_size=20.0,
                avg_price=5.0,
                notional=100.0,
                fee=0.06,
                fee_coin="USDT",
                order_id="1",
                status="filled",
                position_side="short",
            )
        ],
    )
    previous = {
        "positions": json.dumps(
            [{"symbol": "NEARUSDT", "side": "long", "qty": 20.0, "funding_cumulative": -0.5}]
        )
    }

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-03",
        run_at=datetime(2026, 11, 4, 3, 5, tzinfo=timezone.utc),
        prev_equity=100.0,
        capital_flow=0.0,
        warnings=[],
        previous=previous,
    )

    assert entry.funding_total == pytest.approx(-0.08)


def test_track_bootstrap_keeps_inherited_funding_as_a_baseline_only() -> None:
    report = ExecutionReport(
        signal_date="2026-11-14",
        equity_before=500.0,
        equity_after=500.0,
        positions_after=[
            {
                "asset": "near",
                "symbol": "NEARUSDT",
                "total": "9",
                "posSide": "short",
                "avgPrice": "3.2",
                "markPrice": "3.0",
                "totalFunding": "0.125",
            }
        ],
    )

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-14",
        run_at=datetime(2026, 11, 15, 1, 5, tzinfo=timezone.utc),
        prev_equity=None,
        capital_flow=0.0,
        warnings=[],
        bootstrap_track=True,
    )

    assert entry.funding_total == 0.0
    assert entry.positions[0]["funding_cumulative"] == pytest.approx(0.125)


def test_journal_includes_funding_from_a_position_closed_during_the_day() -> None:
    report = ExecutionReport(
        signal_date="2026-11-03",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[],
    )
    previous = {
        "positions": json.dumps(
            [{"symbol": "NEARUSDT", "side": "long", "qty": 20.0, "funding_cumulative": -0.10}]
        )
    }

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-03",
        run_at=datetime(2026, 11, 4, 3, 5, tzinfo=timezone.utc),
        prev_equity=100.0,
        capital_flow=0.0,
        warnings=[],
        previous=previous,
        closed_position_funding={"NEARUSDT": -0.04},
    )

    assert entry.funding_total == pytest.approx(-0.04)


def test_journal_does_not_apply_the_previous_funding_baseline_twice() -> None:
    report = ExecutionReport(
        signal_date="2026-11-03",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[],
    )
    previous = {
        "positions": json.dumps(
            [{"symbol": "NEARUSDT", "side": "long", "qty": 20.0, "funding_cumulative": -0.10}]
        )
    }

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-03",
        run_at=datetime(2026, 11, 4, 3, 5, tzinfo=timezone.utc),
        prev_equity=100.0,
        capital_flow=0.0,
        warnings=[],
        previous=previous,
        closed_position_funding={"NEARUSDT": -0.04},
    )

    assert entry.funding_total == pytest.approx(-0.04)


def test_closed_funding_history_only_counts_a_finished_position_cycle() -> None:
    previous = {
        "positions": json.dumps(
            [{"symbol": "NEARUSDT", "side": "long", "qty": 20.0, "funding_cumulative": -0.10}]
        )
    }
    history = [
        {
            "symbol": "NEARUSDT",
            "posSide": "long",
            "updatedTime": "1793750400000",
            "totalFunding": "-0.04",
        }
    ]

    funding, notes = execute_live_plan._closed_funding_from_history(
        history,
        previous=previous,
        current_positions=[],
        fills=[],
        previous_run_at="2026-11-03T03:05:00+00:00",
        run_at="2026-11-04T03:05:00+00:00",
    )

    assert funding == {"NEARUSDT": pytest.approx(-0.04)}
    assert notes == []


def test_closed_funding_history_subtracts_only_the_carryover_cycle_baseline() -> None:
    previous = {
        "positions": json.dumps(
            [{"symbol": "NEARUSDT", "side": "long", "qty": 20.0, "funding_cumulative": -0.10}]
        )
    }
    previous_at = pd.Timestamp("2026-11-03T03:05:00+00:00")
    run_at = pd.Timestamp("2026-11-04T03:05:00+00:00")
    history = [
        {
            "positionId": "carryover",
            "symbol": "NEARUSDT",
            "posSide": "long",
            "createdTime": int((previous_at - pd.Timedelta(days=1)).timestamp() * 1000),
            "updatedTime": int((previous_at + pd.Timedelta(hours=9)).timestamp() * 1000),
            "totalFunding": "-0.14",
        },
        {
            "positionId": "intraday-reopen",
            "symbol": "NEARUSDT",
            "posSide": "long",
            "createdTime": int((previous_at + pd.Timedelta(hours=10)).timestamp() * 1000),
            "updatedTime": int((run_at - pd.Timedelta(hours=1)).timestamp() * 1000),
            "totalFunding": "-0.02",
        },
    ]

    funding, notes = execute_live_plan._closed_funding_from_history(
        history,
        previous=previous,
        current_positions=[],
        fills=[],
        previous_run_at=previous_at,
        run_at=run_at,
    )

    assert funding == {"NEARUSDT": pytest.approx(-0.06)}
    assert notes == []


def test_closed_funding_history_is_not_needed_for_a_position_that_still_held() -> None:
    previous = {
        "positions": json.dumps(
            [{"symbol": "NEARUSDT", "side": "long", "qty": 20.0, "funding_cumulative": -0.10}]
        )
    }

    funding, notes = execute_live_plan._closed_funding_from_history(
        [
            {
                "symbol": "NEARUSDT",
                "posSide": "long",
                "updatedTime": "1793750400000",
                "totalFunding": "-0.04",
            }
        ],
        previous=previous,
        current_positions=[{"symbol": "NEARUSDT", "posSide": "long", "total": "20"}],
        fills=[],
        previous_run_at="2026-11-03T03:05:00+00:00",
        run_at="2026-11-04T03:05:00+00:00",
    )

    assert funding == {}
    assert notes == []


def test_execution_window_refuses_to_trade_before_the_signal_hint() -> None:
    error = execute_live_plan._execution_window_error(
        execution_hint=datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc),
        now=datetime(2026, 11, 4, 2, 59, tzinfo=timezone.utc),
        catchup_hours=6.0,
        allow_late=False,
    )

    assert error is not None
    assert "not due" in error


def test_execution_window_requires_explicit_permission_after_six_hours() -> None:
    hint = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
    now = datetime(2026, 11, 4, 9, 1, tzinfo=timezone.utc)

    assert execute_live_plan._execution_window_error(
        execution_hint=hint, now=now, catchup_hours=6.0, allow_late=False
    ) is not None
    assert execute_live_plan._execution_window_error(
        execution_hint=hint, now=now, catchup_hours=6.0, allow_late=True
    ) is None


def test_live_execution_requires_a_manifest_even_for_a_recent_event_book(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts import execute_live_plan

    now = datetime.now(timezone.utc)
    signal_date = pd.Timestamp(now - pd.Timedelta(hours=3))
    event_hint = signal_date + pd.Timedelta(days=1, hours=3)
    monkeypatch.setattr(
        execute_live_plan,
        "load_latest_targets",
        lambda _: (
            signal_date,
            event_hint,
            pd.DataFrame([{"asset": "near", "target_weight": 0.0}]),
        ),
    )
    args = execute_live_plan.parse_args(
        [
            "--live",
            "--manifest-file",
            str(tmp_path / "missing-manifest.json"),
            "--allow-late-execution",
        ]
    )

    with pytest.raises(SystemExit, match="manifest"):
        execute_live_plan._main(args)


def test_live_execution_rejects_a_manifest_without_evaluation_dates(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts import execute_live_plan

    now = datetime.now(timezone.utc)
    signal_date = pd.Timestamp(now - pd.Timedelta(hours=27))
    execution_hint = signal_date + pd.Timedelta(days=1, hours=3)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(_valid_manifest_payload(last_mark=now.isoformat())),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        execute_live_plan,
        "load_latest_targets",
        lambda _: (
            signal_date,
            execution_hint,
            pd.DataFrame([{"asset": "near", "target_weight": 0.0}]),
        ),
    )
    monkeypatch.setattr(
        execute_live_plan,
        "load_symbol_map",
        lambda _: (_ for _ in ()).throw(RuntimeError("continued past manifest")),
    )
    args = execute_live_plan.parse_args(["--manifest-file", str(manifest)])

    with pytest.raises(SystemExit, match="manifest"):
        execute_live_plan._main(args)


def test_manifest_event_freshness_requires_today_s_new_target_row() -> None:
    signal_date = pd.Timestamp("2026-11-13T00:00:00Z")

    assert execute_live_plan._target_event_is_fresh(
        signal_date, {"signal_end_date": "2026-11-13"}
    )
    assert not execute_live_plan._target_event_is_fresh(
        signal_date, {"signal_end_date": "2026-11-14"}
    )


def test_live_execution_uses_the_daily_manifest_hint_for_an_unchanged_event_book(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts import execute_live_plan

    now = datetime.now(timezone.utc)
    event_signal_date = pd.Timestamp(now - pd.Timedelta(days=8))
    event_hint = event_signal_date + pd.Timedelta(days=1, hours=3)
    signal_end = (now - pd.Timedelta(hours=27)).date()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            _valid_manifest_payload(
                last_mark=now.isoformat(),
                index_end_date=signal_end.isoformat(),
                signal_end_date=signal_end.isoformat(),
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        execute_live_plan,
        "load_latest_targets",
        lambda _: (
            event_signal_date,
            event_hint,
            pd.DataFrame([{"asset": "near", "target_weight": 0.0}]),
        ),
    )
    seen: list[pd.Timestamp] = []

    def stop_at_window_check(*, execution_hint, **_kwargs):
        seen.append(pd.Timestamp(execution_hint))
        return "stop after capturing the effective execution hint"

    monkeypatch.setattr(execute_live_plan, "_execution_window_error", stop_at_window_check)
    args = execute_live_plan.parse_args(["--manifest-file", str(manifest)])

    with pytest.raises(SystemExit, match="stop after capturing"):
        execute_live_plan._main(args)

    assert seen == [
        pd.Timestamp(signal_end, tz="UTC") + pd.Timedelta(days=1, hours=1, minutes=5)
    ]


def test_execution_lock_allows_only_one_live_process(tmp_path) -> None:
    from scripts.execute_live_plan import _acquire_execution_lock, _release_execution_lock

    path = tmp_path / "execution.lock"
    first = _acquire_execution_lock(path)
    second = _acquire_execution_lock(path)

    assert first is not None
    assert second is None

    _release_execution_lock(first)
    third = _acquire_execution_lock(path)
    assert third is not None
    _release_execution_lock(third)


def _attempt_order(action: str, reduce_only: bool) -> OrderIntent:
    return OrderIntent(
        asset="near",
        symbol="NEARUSDT",
        action=action,
        side="sell" if reduce_only else "buy",
        size=1.0,
        price=5.0,
        notional=5.0,
        reduce_only=reduce_only,
        reason="test",
    )


def test_equity_floor_keeps_risk_reducing_orders_and_blocks_new_risk() -> None:
    close = _attempt_order("CLOSE", True)
    increase = _attempt_order("INCREASE", False)
    plan = ExecutionPlan(
        equity=10.0,
        leverage=2.0,
        target_margin_ratio=0.515,
        orders=[close, increase],
        margin_intents=[
            MarginIntent("near", "NEARUSDT", "long", "add", 1.0, "test")
        ],
        warnings=[],
        target_notional={"near": 50.0},
        expected_gross_notional=50.0,
        expected_margin=25.75,
    )

    filtered, blocked = execute_live_plan._apply_equity_floor(plan, floor_usdt=20.0)

    assert filtered.orders == [close]
    assert filtered.margin_intents == []
    assert blocked == [increase]
    assert any("below" in warning and "risk-reducing" in warning for warning in filtered.warnings)


def test_execution_attempt_prefix_changes_only_after_a_run_was_persisted() -> None:
    key = "SPEC|2026-11-13|2026-11-14"
    first = execute_live_plan._attempt_client_oid_prefix(key, {"runs": []})
    crashed = execute_live_plan._attempt_client_oid_prefix(
        key,
        {"runs": [{"key": "OTHER|2026-11-13|2026-11-14", "status": "partial"}]},
    )
    retried = execute_live_plan._attempt_client_oid_prefix(
        key,
        {"runs": [{"key": key, "status": "partial"}]},
    )

    assert crashed == first
    assert retried != first


def test_execution_attempt_prefix_is_scoped_to_the_bitget_account() -> None:
    key = "SPEC|2026-11-13|2026-11-14"

    account_a = execute_live_plan._attempt_client_oid_prefix(key, {"runs": []}, account_fp="account-a")
    account_b = execute_live_plan._attempt_client_oid_prefix(key, {"runs": []}, account_fp="account-b")

    assert account_a != account_b


def test_live_executor_fatal_error_writes_json_and_notifies(tmp_path, monkeypatch) -> None:
    from scripts import execute_live_plan

    monkeypatch.setenv("ATLAS20_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "123")
    sent: list[str] = []
    monkeypatch.setattr(
        execute_live_plan,
        "_main",
        lambda args: (_ for _ in ()).throw(RuntimeError("exchange unavailable")),
    )
    monkeypatch.setattr(
        execute_live_plan,
        "send_telegram_message",
        lambda message, **kwargs: sent.append(message),
    )
    out = tmp_path / "latest.json"

    code = execute_live_plan.main(
        [
            "--live",
            "--notify",
            "--json-out",
            str(out),
            "--lock-file",
            str(tmp_path / "execution.lock"),
        ]
    )

    assert code == 1
    assert sent and "exchange unavailable" in sent[0]
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "error"


def test_protect_only_bypasses_target_replanning_but_obeys_the_kill_switch(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        execute_live_plan,
        "_protect_only_main",
        lambda _args: calls.append("protect") or 0,
    )
    monkeypatch.setattr(
        execute_live_plan,
        "load_latest_targets",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("protect-only loaded a new target plan")
        ),
    )
    code = execute_live_plan.main(
        [
            "--live",
            "--protect-only",
            "--kill-switch",
            str(tmp_path / "missing.kill"),
            "--json-out",
            str(tmp_path / "protect.json"),
            "--lock-file",
            str(tmp_path / "execution.lock"),
        ]
    )
    assert code == 0
    assert calls == ["protect"]

    kill = tmp_path / "KILL"
    kill.write_text("stop", encoding="utf-8")
    blocked = execute_live_plan.main(
        [
            "--live",
            "--protect-only",
            "--kill-switch",
            str(kill),
            "--json-out",
            str(tmp_path / "protect-error.json"),
            "--lock-file",
            str(tmp_path / "execution.lock"),
        ]
    )
    assert blocked == 1
    assert calls == ["protect"]


def test_reconcile_only_runs_before_the_kill_switch_and_places_no_orders(
    tmp_path: Path, monkeypatch
) -> None:
    kill = tmp_path / "KILL"
    kill.write_text("stop new risk", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        execute_live_plan,
        "_reconcile_only_main",
        lambda _args: calls.append("reconcile") or 0,
    )
    monkeypatch.setattr(
        execute_live_plan,
        "execute_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("reconcile-only planned an order")
        ),
    )

    code = execute_live_plan.main(
        [
            "--live",
            "--reconcile-only",
            "--kill-switch",
            str(kill),
            "--lock-file",
            str(tmp_path / "execution.lock"),
        ]
    )

    assert code == 0
    assert calls == ["reconcile"]


def test_lock_acquisition_failure_also_writes_a_fatal_report(tmp_path, monkeypatch) -> None:
    from scripts import execute_live_plan

    monkeypatch.setattr(
        execute_live_plan,
        "_acquire_execution_lock",
        lambda _: (_ for _ in ()).throw(OSError("lock unavailable")),
    )
    out = tmp_path / "latest.json"

    code = execute_live_plan.main(
        [
            "--live",
            "--json-out",
            str(out),
            "--lock-file",
            str(tmp_path / "execution.lock"),
        ]
    )

    assert code == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert "lock unavailable" in payload["error"]


def test_dry_run_does_not_take_the_live_execution_lock(tmp_path, monkeypatch) -> None:
    from scripts import execute_live_plan

    monkeypatch.setattr(
        execute_live_plan,
        "_acquire_execution_lock",
        lambda _: (_ for _ in ()).throw(AssertionError("dry run took the live lock")),
    )
    monkeypatch.setattr(execute_live_plan, "_main", lambda args: 0)

    code = execute_live_plan.main(
        ["--lock-file", str(tmp_path / "execution.lock")]
    )

    assert code == 0


def test_fatal_notification_survives_an_unwritable_latest_path(tmp_path, monkeypatch) -> None:
    from scripts import execute_live_plan

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    sent: list[str] = []
    monkeypatch.setenv("ATLAS20_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(
        execute_live_plan,
        "_main",
        lambda args: (_ for _ in ()).throw(RuntimeError("execution failed")),
    )
    monkeypatch.setattr(
        execute_live_plan,
        "send_telegram_message",
        lambda message, **kwargs: sent.append(message),
    )

    code = execute_live_plan.main(
        [
            "--live",
            "--notify",
            "--json-out",
            str(blocker / "latest.json"),
            "--lock-file",
            str(tmp_path / "execution.lock"),
        ]
    )

    assert code == 1
    assert sent and "execution failed" in sent[0]


def test_stamp_assets_overrides_a_venue_alias_with_the_model_asset() -> None:
    from scripts import execute_live_plan

    stamped = execute_live_plan._stamp_assets(
        [{"symbol": "TRXUSDT", "asset": "TRX", "total": "10"}],
        {"tron": "TRXUSDT"},
    )

    assert stamped[0]["asset"] == "tron"


def test_execution_key_changes_when_the_target_book_changes() -> None:
    first = execute_live_plan._execution_key(
        "spec",
        "2026-11-06",
        "2026-11-14",
        "target-a",
    )
    second = execute_live_plan._execution_key(
        "spec",
        "2026-11-06",
        "2026-11-14",
        "target-b",
    )

    assert first.endswith("|2026-11-14")
    assert second.endswith("|2026-11-14")
    assert first != second


def test_active_event_targets_store_quantities_at_the_event_size() -> None:
    from atlas20.derivatives.execution import ContractSpec

    plan = ExecutionPlan(
        equity=500.0,
        leverage=2.0,
        target_margin_ratio=0.515,
        orders=[],
        margin_intents=[],
        warnings=[],
        target_notional={"near": 50.0},
        expected_gross_notional=50.0,
        expected_margin=25.75,
        signed_target_notional={"near": -50.0},
    )

    quantities = execute_live_plan._event_target_quantities(
        plan,
        {"near": -0.1},
        {"near": ContractSpec("NEARUSDT")},
        {"near": 5.0},
    )

    assert quantities == {"NEARUSDT": pytest.approx(10.0)}


def _venue_stop_fill(**overrides):
    payload = {
        "asset": "near",
        "symbol": "NEARUSDT",
        "action": "CLOSE",
        "side": "buy",
        "stop_loss": 6.0,
        "requested_size": 10.0,
        "filled_size": 10.0,
        "avg_price": 6.1,
        "notional": 61.0,
        "fee": 0.0366,
        "fee_coin": "USDT",
        "order_id": "executed-stop-1",
        "status": "filled",
        "position_side": "short",
        "requested_stop_loss": 6.0,
        "stop_trigger_by": "mark",
        "stop_order_type": "market",
        "reason": "venue_strategy_stop",
        "strategy_order_id": "strategy-stop-1",
        "triggered_at": "2026-11-15T00:00:00+00:00",
    }
    payload.update(overrides)
    return OrderFill(**payload)


def test_venue_stop_fill_must_match_the_open_journal_short_cycle() -> None:
    errors = execute_live_plan._venue_stop_reconciliation_errors(
        [_venue_stop_fill()],
        expected_stops={"NEARUSDT": 6.0},
        expected_short_qty={"NEARUSDT": 10.0},
    )

    assert errors == []


def test_venue_stop_fill_with_no_journaled_short_cycle_is_a_failure() -> None:
    errors = execute_live_plan._venue_stop_reconciliation_errors(
        [_venue_stop_fill()],
        expected_stops={},
        expected_short_qty={},
    )

    assert len(errors) == 1
    assert "no open journal short" in errors[0]["error"]


class _StopHistoryClient:
    def __init__(self, trigger_ms: int = 1_794_700_800_000) -> None:
        self.trigger_ms = int(trigger_ms)
        self.strategy_window = None
        self.order_window = None

    def strategy_order_history(self, **kwargs):
        self.strategy_window = kwargs
        return [
            {
                "orderId": "strategy-stop-1",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "side": "buy",
                "type": "tpsl",
                "status": "success",
                "qty": "10",
                "stopLoss": "6",
                "slTriggerBy": "mark",
                "slOrderType": "market",
                "updatedTime": str(self.trigger_ms),
            }
        ]

    def order_history_all(self, **kwargs):
        self.order_window = kwargs
        return [
            {
                "orderId": "executed-stop-1",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "side": "buy",
                "orderStatus": "filled",
                "qty": "10",
                "cumExecQty": "10",
                "avgPrice": "6.1",
                "cumExecValue": "61",
                "feeDetail": [{"fee": "0.0366", "feeCoin": "USDT"}],
                "createdTime": str(self.trigger_ms + 5),
                "updatedTime": str(self.trigger_ms + 6),
                "clientOid": "generated-close",
            }
        ]


def test_recovery_imports_a_strategy_stop_once_and_links_it_to_the_short_cycle() -> None:
    journal = pd.DataFrame(
        [
            JournalEntry(
                date="2026-11-14",
                run_at_utc="2026-11-14T16:38:00+00:00",
                signal_date="2026-11-13",
                equity=500.0,
                position_value=50.0,
                cash=450.0,
                day_pnl=0.0,
                day_return=0.0,
                fees_today=0.0,
                funding_total=0.0,
                unrealised_pnl=0.0,
                positions=[
                    {
                        "symbol": "NEARUSDT",
                        "side": "short",
                        "qty": 10.0,
                        "normalized_stop_loss": 6.0,
                    }
                ],
                trades=[
                    {
                        "order_id": "entry-1",
                        "symbol": "NEARUSDT",
                        "action": "OPEN",
                        "side": "sell",
                        "qty": 10.0,
                        "status": "filled",
                        "stop_loss": 6.0,
                        "requested_stop_loss": 6.0,
                        "stop_trigger_by": "mark",
                        "stop_order_type": "market",
                    }
                ],
            ).as_row()
        ]
    )
    client = _StopHistoryClient()

    fills, errors = execute_live_plan._recover_venue_stop_fills(
        client,
        journal=journal,
        state={"last_run_at": "2026-11-14T16:38:00+00:00"},
        symbol_assets={"NEARUSDT": "near"},
        run_at=datetime(2026, 11, 15, 1, 5, tzinfo=timezone.utc),
    )

    assert errors == []
    assert [fill.order_id for fill in fills] == ["executed-stop-1"]
    assert fills[0].reason == "venue_strategy_stop"
    assert client.strategy_window["start_time_ms"] < 1794700800000
    assert client.order_window["end_time_ms"] > 1794700800000


def test_journal_preserves_strategy_stop_provenance() -> None:
    report = ExecutionReport(
        signal_date="2026-11-13",
        equity_before=500.0,
        equity_after=500.0,
        positions_after=[],
        fills=[_venue_stop_fill()],
    )

    entry = execute_live_plan._journal_entry(
        report,
        signal_date="2026-11-13",
        run_at=datetime(2026, 11, 15, 1, 5, tzinfo=timezone.utc),
        prev_equity=500.0,
        capital_flow=0.0,
        warnings=[],
    )

    trade = entry.trades[0]
    assert trade["reason"] == "venue_strategy_stop"
    assert trade["strategy_order_id"] == "strategy-stop-1"
    assert trade["triggered_at"] == "2026-11-15T00:00:00+00:00"


def test_active_event_record_freezes_signal_date_and_position_targets() -> None:
    from atlas20.derivatives.execution import ContractSpec

    plan = ExecutionPlan(
        equity=500.0,
        leverage=2.0,
        target_margin_ratio=0.515,
        orders=[],
        margin_intents=[],
        warnings=[],
        target_notional={"near": 50.0},
        expected_gross_notional=50.0,
        expected_margin=25.75,
        signed_target_notional={"near": -50.0},
    )

    record = execute_live_plan._active_event_record(
        plan,
        {"near": -0.1},
        {"near": ContractSpec("NEARUSDT")},
        {"near": 5.0},
        signal_date=pd.Timestamp("2026-11-13T00:00:00Z"),
        target_identity="sha256:target",
        execution_hint=pd.Timestamp("2026-11-14T01:05:00Z"),
        applied_at="2026-11-14T01:10:00+00:00",
        failures=[],
    )

    assert record["signal_date"] == "2026-11-13"
    assert record["targets_sha256"] == "sha256:target"
    assert record["position_status"] == "ok"
    assert record["target_quantities"] == {"NEARUSDT": pytest.approx(10.0)}


def test_margin_only_failure_keeps_event_position_application_ok() -> None:
    failures = [
        {
            "symbol": "NEARUSDT",
            "action": "MARGIN",
            "side": "short",
            "size": "1",
            "error": "margin rejected",
        }
    ]

    assert execute_live_plan._position_application_failures(failures) == []


def test_persisted_state_keeps_the_active_target_event(tmp_path: Path) -> None:
    entry = JournalEntry(
        date="2026-11-14",
        run_at_utc="2026-11-14T16:38:00+00:00",
        signal_date="2026-11-13",
        equity=500.0,
        position_value=50.0,
        cash=450.0,
        day_pnl=0.0,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
    )
    state_path = tmp_path / "state.json"
    active_event = {
        "signal_date": "2026-11-13",
        "targets_sha256": "sha256:target",
        "target_quantities": {"NEARUSDT": 10.0},
        "position_status": "ok",
        "stopped_symbols": {},
    }

    execute_live_plan._persist_run_result(
        json_out=tmp_path / "latest.json",
        payload={"status": "ok"},
        journal_file=tmp_path / "journal.csv",
        entry=entry,
        state_file=state_path,
        key="SPEC|2026-11-13|2026-11-14",
        status="ok",
        report=ExecutionReport(signal_date="2026-11-13"),
        account_fp="account-fingerprint",
        active_event=active_event,
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["active_event"] == active_event


def test_active_event_records_confirmed_venue_stop_without_clearing_target_book() -> None:
    event = {
        "signal_date": "2026-11-13",
        "target_quantities": {"NEARUSDT": 10.0},
        "stopped_symbols": {},
    }

    merged = execute_live_plan._record_stopped_fills(
        event,
        [_venue_stop_fill()],
    )

    assert merged["target_quantities"] == {"NEARUSDT": 10.0}
    assert merged["stopped_symbols"] == {
        "NEARUSDT": {
            "order_id": "executed-stop-1",
            "strategy_order_id": "strategy-stop-1",
            "triggered_at": "2026-11-15T00:00:00+00:00",
            "quantity": 10.0,
            "requested_quantity": 10.0,
            "stop_loss": 6.0,
            "stop_trigger_by": "mark",
            "stop_order_type": "market",
        }
    }


def test_current_reconciliation_stop_blocks_reopen_even_before_event_applied_at() -> None:
    event = {
        "applied_at": "2026-11-15T01:06:00+00:00",
        "stopped_symbols": {},
    }

    merged = execute_live_plan._record_stopped_fills(
        event,
        [_venue_stop_fill(triggered_at="2026-11-15T00:30:00+00:00")],
        include_before_application=True,
    )

    assert merged["stopped_symbols"]["NEARUSDT"]["order_id"] == "executed-stop-1"


def test_new_target_event_does_not_mark_a_prior_cycle_stop_as_current() -> None:
    event = {
        "signal_date": "2026-11-15",
        "applied_at": "2026-11-15T01:05:00+00:00",
        "target_quantities": {"NEARUSDT": 9.0},
        "stopped_symbols": {},
    }

    merged = execute_live_plan._record_stopped_fills(
        event,
        [_venue_stop_fill()],
    )

    assert merged["stopped_symbols"] == {}


def test_stop_recovery_uses_its_last_successful_high_water_mark() -> None:
    trigger_ms = int(
        pd.Timestamp("2026-11-14T10:00:00Z").timestamp() * 1000
    )
    journal = pd.DataFrame(
        [
            JournalEntry(
                date="2026-11-14",
                run_at_utc="2026-11-14T16:38:00+00:00",
                signal_date="2026-11-13",
                equity=500.0,
                position_value=50.0,
                cash=450.0,
                day_pnl=0.0,
                day_return=0.0,
                fees_today=0.0,
                funding_total=0.0,
                unrealised_pnl=0.0,
                positions=[
                    {
                        "symbol": "NEARUSDT",
                        "side": "short",
                        "qty": 10.0,
                        "normalized_stop_loss": 6.0,
                    }
                ],
                trades=[
                    {
                        "order_id": "entry-1",
                        "symbol": "NEARUSDT",
                        "action": "OPEN",
                        "side": "sell",
                        "qty": 10.0,
                        "status": "filled",
                        "stop_loss": 6.0,
                        "requested_stop_loss": 6.0,
                        "stop_trigger_by": "mark",
                        "stop_order_type": "market",
                    }
                ],
            ).as_row()
        ]
    )
    client = _StopHistoryClient(trigger_ms=trigger_ms)

    fills, errors = execute_live_plan._recover_venue_stop_fills(
        client,
        journal=journal,
        state={
            "last_run_at": "2026-11-14T16:38:00+00:00",
            "stop_reconciliation_through": "2026-11-14T00:00:00+00:00",
        },
        symbol_assets={"NEARUSDT": "near"},
        run_at=datetime(2026, 11, 15, 1, 5, tzinfo=timezone.utc),
    )

    assert errors == []
    assert len(fills) == 1
    assert client.strategy_window["start_time_ms"] <= trigger_ms


def test_stop_recovery_rescans_a_late_arriving_history_row_beyond_one_hour() -> None:
    trigger_ms = int(
        pd.Timestamp("2026-11-14T10:00:00Z").timestamp() * 1000
    )
    journal = pd.DataFrame(
        [
            JournalEntry(
                date="2026-11-14",
                run_at_utc="2026-11-14T09:00:00+00:00",
                signal_date="2026-11-13",
                equity=500.0,
                position_value=50.0,
                cash=450.0,
                day_pnl=0.0,
                day_return=0.0,
                fees_today=0.0,
                funding_total=0.0,
                unrealised_pnl=0.0,
                positions=[
                    {
                        "symbol": "NEARUSDT",
                        "side": "short",
                        "qty": 10.0,
                        "normalized_stop_loss": 6.0,
                    }
                ],
                trades=[
                    {
                        "order_id": "entry-1",
                        "symbol": "NEARUSDT",
                        "action": "OPEN",
                        "side": "sell",
                        "qty": 10.0,
                        "status": "filled",
                        "stop_loss": 6.0,
                        "requested_stop_loss": 6.0,
                        "stop_trigger_by": "mark",
                        "stop_order_type": "market",
                    }
                ],
            ).as_row()
        ]
    )
    client = _StopHistoryClient(trigger_ms=trigger_ms)

    fills, errors = execute_live_plan._recover_venue_stop_fills(
        client,
        journal=journal,
        state={
            "last_run_at": "2026-11-14T16:00:00+00:00",
            "stop_reconciliation_through": "2026-11-14T16:00:00+00:00",
        },
        symbol_assets={"NEARUSDT": "near"},
        run_at=datetime(2026, 11, 14, 17, 0, tzinfo=timezone.utc),
    )

    assert errors == []
    assert len(fills) == 1
    assert client.strategy_window["start_time_ms"] <= trigger_ms


def test_persisted_state_advances_stop_reconciliation_high_water(tmp_path: Path) -> None:
    entry = JournalEntry(
        date="2026-11-15",
        run_at_utc="2026-11-15T01:05:00+00:00",
        signal_date="2026-11-13",
        equity=500.0,
        position_value=50.0,
        cash=450.0,
        day_pnl=0.0,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
    )
    state_path = tmp_path / "state.json"

    execute_live_plan._persist_run_result(
        json_out=tmp_path / "latest.json",
        payload={"status": "ok"},
        journal_file=tmp_path / "journal.csv",
        entry=entry,
        state_file=state_path,
        key="SPEC|2026-11-13|2026-11-15",
        status="ok",
        report=ExecutionReport(signal_date="2026-11-13"),
        stop_reconciliation_through="2026-11-15T01:06:00+00:00",
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["stop_reconciliation_through"] == "2026-11-15T01:06:00+00:00"
    assert state["last_run_mode"] == "execution"
    assert state["runs"][-1]["mode"] == "execution"


def test_dry_run_does_not_write_live_state_or_journal(tmp_path: Path, monkeypatch) -> None:
    from atlas20.derivatives.execution import AccountState

    class _Client:
        def account_info(self):
            return {
                "userId": "dry-run-user",
                "permType": "read_and_write",
                "permissions": ["uta_trade", "uta_mgt"],
            }

        def account_assets(self):
            return {"usdtEquity": "100", "assets": [{"coin": "USDT", "available": "100"}]}

        def current_positions(self):
            return []

    prices = tmp_path / "prices.json"
    prices.write_text("{}", encoding="utf-8")
    state = tmp_path / "state.json"
    journal = tmp_path / "journal.csv"
    latest = tmp_path / "latest.json"
    signal_date = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1)

    monkeypatch.setenv("ATLAS20_BITGET_API_KEY", "test-key")
    monkeypatch.setenv("ATLAS20_BITGET_SECRET_KEY", "test-secret")
    monkeypatch.setenv("ATLAS20_BITGET_PASSPHRASE", "test-pass")
    monkeypatch.setattr(execute_live_plan, "BitgetPrivateClient", lambda _: _Client())
    monkeypatch.setattr(
        execute_live_plan,
        "load_latest_targets",
        lambda _: (
            signal_date,
            signal_date + pd.Timedelta(days=1, hours=1, minutes=5),
            pd.DataFrame(columns=["asset", "target_weight"]),
        ),
    )
    monkeypatch.setattr(execute_live_plan, "load_symbol_map", lambda _: {})
    monkeypatch.setattr(execute_live_plan, "fetch_public_instruments", lambda _: [])
    monkeypatch.setattr(execute_live_plan, "specs_from_instruments", lambda *_: {})
    monkeypatch.setattr(
        execute_live_plan,
        "account_state_from_bitget",
        lambda *_: AccountState(equity=100.0, available_margin=100.0),
    )
    monkeypatch.setattr(
        execute_live_plan,
        "_persist_run_result",
        lambda **_: (_ for _ in ()).throw(
            AssertionError("dry run wrote live state")
        ),
    )
    monkeypatch.setattr(
        execute_live_plan,
        "_event_completion_issues",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry run compared planned orders with the untouched venue book")
        ),
    )

    args = execute_live_plan.parse_args(
        [
            "--allow-late-execution",
            "--prices-file",
            str(prices),
            "--state-file",
            str(state),
            "--journal-file",
            str(journal),
            "--json-out",
            str(latest),
            "--kill-switch",
            str(tmp_path / "missing.kill"),
        ]
    )

    assert execute_live_plan._main(args) == 0
    assert not state.exists()
    assert not journal.exists()
    assert not latest.exists()



def test_next_day_partial_event_wires_frozen_quantities_into_the_plan(
    tmp_path: Path, monkeypatch
) -> None:
    from atlas20.derivatives.execution import AccountState, ContractSpec

    class _Client:
        def account_info(self):
            return {"userId": "account-a"}

        def current_positions(self):
            return []

    signal_date = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1)
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "account_fingerprint": "account-a",
                "last_key": "SPEC|old",
                "last_status": "partial",
                "active_event": {
                    "signal_date": str(signal_date.date()),
                    "targets_sha256": "",
                    "execution_hint": "2026-11-15T01:05:00+00:00",
                    "applied_at": "2026-11-15T01:06:00+00:00",
                    "equity_at_execution": 500.0,
                    "target_weights": {"near": -0.1},
                    "prices": {"near": 5.0},
                    "target_quantities": {"NEARUSDT": 10.0},
                    "position_status": "partial",
                    "position_failures": [{"symbol": "*", "action": "VERIFY"}],
                    "stopped_symbols": {},
                },
            }
        ),
        encoding="utf-8",
    )
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"NEARUSDT": 5.0}), encoding="utf-8")
    seen: dict = {}

    def capture_plan(account, targets, specs, prices_by_asset, **kwargs):
        seen.update(
            account=account,
            targets=targets,
            prices=prices_by_asset,
            kwargs=kwargs,
        )
        return ExecutionPlan(
            equity=account.equity,
            leverage=2.0,
            target_margin_ratio=0.515,
            orders=[],
            margin_intents=[],
            warnings=[],
            target_notional={},
            expected_gross_notional=0.0,
            expected_margin=0.0,
            signed_target_notional={},
        )

    monkeypatch.setenv("ATLAS20_BITGET_API_KEY", "test-key")
    monkeypatch.setenv("ATLAS20_BITGET_SECRET_KEY", "test-secret")
    monkeypatch.setenv("ATLAS20_BITGET_PASSPHRASE", "test-pass")
    monkeypatch.setattr(execute_live_plan, "BitgetPrivateClient", lambda _: _Client())
    monkeypatch.setattr(execute_live_plan, "account_fingerprint", lambda _: "account-a")
    monkeypatch.setattr(
        execute_live_plan,
        "load_latest_targets",
        lambda _: (
            signal_date,
            signal_date + pd.Timedelta(days=1, hours=1, minutes=5),
            pd.DataFrame([{"asset": "near", "target_weight": -0.1}]),
        ),
    )
    monkeypatch.setattr(execute_live_plan, "load_symbol_map", lambda _: {"near": "NEARUSDT"})
    monkeypatch.setattr(execute_live_plan, "fetch_public_instruments", lambda _: [])
    monkeypatch.setattr(
        execute_live_plan,
        "specs_from_instruments",
        lambda *_: {"near": ContractSpec("NEARUSDT", min_order_qty=1.0)},
    )
    monkeypatch.setattr(
        execute_live_plan,
        "account_state_from_bitget",
        lambda *_: AccountState(equity=500.0, available_margin=0.0),
    )
    monkeypatch.setattr(execute_live_plan, "build_execution_plan", capture_plan)
    monkeypatch.setattr(execute_live_plan, "_event_completion_issues", lambda *_, **__: [])

    args = execute_live_plan.parse_args(
        [
            "--allow-late-execution",
            "--allow-stale-signal",
            "--manifest-file",
            str(tmp_path / "missing-manifest.json"),
            "--prices-file",
            str(prices),
            "--state-file",
            str(state_path),
            "--journal-file",
            str(tmp_path / "journal.csv"),
            "--json-out",
            str(tmp_path / "latest.json"),
            "--kill-switch",
            str(tmp_path / "missing.kill"),
        ]
    )

    assert execute_live_plan._main(args) == 0
    assert seen["kwargs"]["rebalance_to_target"] is True
    assert seen["kwargs"]["target_quantities"] == {"near": -10.0}


def test_event_plan_mode_uses_frozen_quantities_only_for_a_partial_active_event() -> None:
    partial = {
        "signal_date": "2026-11-13",
        "targets_sha256": "target-a",
        "position_status": "partial",
    }
    complete = {**partial, "position_status": "ok"}

    assert execute_live_plan._event_plan_mode(
        fresh_target_event=True, active_event=None
    ) == "fresh"
    assert execute_live_plan._event_plan_mode(
        fresh_target_event=True, active_event=partial
    ) == "complete"
    assert execute_live_plan._event_plan_mode(
        fresh_target_event=False, active_event=partial
    ) == "complete"
    assert execute_live_plan._event_plan_mode(
        fresh_target_event=False, active_event=complete
    ) == "maintain"


def test_event_quantities_force_every_stopped_symbol_flat() -> None:
    quantities = execute_live_plan._signed_event_target_quantities(
        {
            "target_weights": {"near": -0.0625, "zcash": -0.07},
            "target_quantities": {"NEARUSDT": 9.0, "ZECUSDT": 0.035},
        },
        {"near": "NEARUSDT", "zcash": "ZECUSDT"},
        {"NEARUSDT": {"order_id": "stop-1"}},
    )

    assert quantities == {"near": 0.0, "zcash": pytest.approx(-0.035)}


def test_event_target_quantities_survive_a_blocked_plan_leg() -> None:
    plan = ExecutionPlan(
        equity=500.0,
        leverage=2.0,
        target_margin_ratio=0.515,
        orders=[],
        margin_intents=[],
        warnings=[],
        target_notional={},
        expected_gross_notional=0.0,
        expected_margin=0.0,
        signed_target_notional={},
    )

    quantities = execute_live_plan._event_target_quantities(
        plan,
        {"near": -0.1},
        {"near": execute_live_plan.ContractSpec("NEARUSDT")},
        {"near": 5.0},
    )

    assert quantities == {"NEARUSDT": pytest.approx(10.0)}


def test_same_event_record_retry_preserves_first_application_and_stops() -> None:
    from atlas20.derivatives.execution import ContractSpec

    plan = ExecutionPlan(
        equity=500.0,
        leverage=2.0,
        target_margin_ratio=0.515,
        orders=[],
        margin_intents=[],
        warnings=[],
        target_notional={"near": 50.0},
        expected_gross_notional=50.0,
        expected_margin=25.75,
        signed_target_notional={"near": -50.0},
    )
    prior = {
        "signal_date": "2026-11-13",
        "targets_sha256": "target-a",
        "execution_hint": "2026-11-14T01:05:00+00:00",
        "applied_at": "2026-11-14T01:06:00+00:00",
        "equity_at_execution": 500.0,
        "target_weights": {"near": -0.1},
        "prices": {"near": 5.0},
        "target_quantities": {"NEARUSDT": 10.0},
        "position_status": "ok",
        "position_failures": [],
        "stopped_symbols": {
            "NEARUSDT": {
                "order_id": "executed-stop-1",
                "strategy_order_id": "strategy-stop-1",
                "triggered_at": "2026-11-15T00:00:00+00:00",
                "quantity": 10.0,
            }
        },
    }

    record = execute_live_plan._active_event_record(
        plan,
        {"near": -0.1},
        {"near": ContractSpec("NEARUSDT")},
        {"near": 5.0},
        signal_date=pd.Timestamp("2026-11-13T00:00:00Z"),
        target_identity="target-a",
        execution_hint=pd.Timestamp("2026-11-14T01:05:00Z"),
        applied_at="2026-11-15T01:06:00+00:00",
        failures=[],
        previous=prior,
    )

    assert record["applied_at"] == prior["applied_at"]
    assert record["stopped_symbols"] == prior["stopped_symbols"]


def test_event_completion_uses_the_effective_risk_overlay_quantity() -> None:
    issues = execute_live_plan._event_completion_issues(
        {
            "target_weights": {"near": -0.1},
            "target_quantities": {"NEARUSDT": 10.0},
            "prices": {"near": 5.0},
            "stopped_symbols": {},
            "risk_overlay": {
                "target_quantities": {"NEARUSDT": 4.0},
                "reason": "risk_cap_scaled",
            },
        },
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "short",
                "total": "4",
                "markPrice": "5",
            }
        ],
        symbol_assets={"NEARUSDT": "near"},
        specs_by_symbol={"NEARUSDT": execute_live_plan.ContractSpec("NEARUSDT")},
    )

    assert issues == []


def test_risk_overlay_snapshot_records_effective_quantities_for_every_target_leg() -> None:
    quantities = execute_live_plan._risk_overlay_quantities(
        {
            "target_weights": {"near": -0.1, "zcash": -0.07},
        },
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "short",
                "total": "4",
            }
        ],
        symbol_assets={"NEARUSDT": "near", "ZECUSDT": "zcash"},
    )

    assert quantities == {"NEARUSDT": 4.0, "ZECUSDT": 0.0}


def test_event_completion_check_flags_a_wrong_signed_position() -> None:
    issues = execute_live_plan._event_completion_issues(
        {
            "target_weights": {"near": -0.1},
            "target_quantities": {"NEARUSDT": 10.0},
            "prices": {"near": 5.0},
            "stopped_symbols": {},
        },
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "long",
                "total": "10",
                "markPrice": "5",
            }
        ],
        symbol_assets={"NEARUSDT": "near"},
        specs_by_symbol={"NEARUSDT": execute_live_plan.ContractSpec("NEARUSDT")},
    )

    assert issues == ["NEARUSDT 目标数量 10 vs 实际 10"]



class _ReconcileStopClient:
    def __init__(self, trigger_ms: int) -> None:
        self.trigger_ms = trigger_ms

    def account_assets(self):
        return {
            "usdtEquity": "500.03",
            "assets": [{"coin": "USDT", "available": "469.00", "balance": "500.03"}],
        }

    def current_positions(self):
        return []

    def strategy_order_history(self, **_kwargs):
        return [
            {
                "orderId": "strategy-stop-1",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "side": "buy",
                "type": "tpsl",
                "status": "success",
                "qty": "10",
                "stopLoss": "6",
                "slTriggerBy": "mark",
                "slOrderType": "market",
                "updatedTime": str(self.trigger_ms),
            }
        ]

    def order_history_all(self, **_kwargs):
        return [
            {
                "orderId": "executed-stop-1",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "side": "buy",
                "orderStatus": "filled",
                "qty": "10",
                "cumExecQty": "10",
                "avgPrice": "6.1",
                "cumExecValue": "61",
                "feeDetail": [{"fee": "0.0366", "feeCoin": "USDT"}],
                "createdTime": str(self.trigger_ms),
                "updatedTime": str(self.trigger_ms),
            }
        ]

    def position_history(self, **_kwargs):
        return [
            {
                "positionId": "near-short-cycle",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "createdTime": str(self.trigger_ms - 172_800_000),
                "updatedTime": str(self.trigger_ms),
                "totalFunding": "0.01",
            }
        ]


def test_reconcile_only_status_never_upgrades_an_incomplete_run() -> None:
    assert execute_live_plan._reconcile_only_status(
        previous_status="partial",
        active_event={"position_status": "ok"},
        stop_errors=[],
    ) == "partial"
    assert execute_live_plan._reconcile_only_status(
        previous_status="ok",
        active_event={"position_status": "partial"},
        stop_errors=[],
    ) == "partial"
    assert execute_live_plan._reconcile_only_status(
        previous_status="ok",
        active_event={"position_status": "ok"},
        stop_errors=[],
    ) == "ok"


def test_reconcile_only_imports_a_post_execution_stop_once_and_attributes_funding(
    tmp_path: Path,
) -> None:
    from atlas20.derivatives.live_journal import load_journal, upsert_entry

    trigger = pd.Timestamp("2026-11-15T02:00:00Z")
    trigger_ms = int(trigger.timestamp() * 1000)
    journal_path = tmp_path / "journal.csv"
    previous = JournalEntry(
        date="2026-11-14",
        run_at_utc="2026-11-14T01:06:00+00:00",
        signal_date="2026-11-13",
        equity=500.0,
        position_value=61.0,
        cash=439.0,
        day_pnl=0.0,
        day_return=0.0,
        fees_today=0.01,
        funding_total=0.004,
        unrealised_pnl=0.0,
        positions=[
            {
                "symbol": "NEARUSDT",
                "side": "short",
                "qty": 10.0,
                "normalized_stop_loss": 6.0,
                "funding_cumulative": 0.004,
            }
        ],
        trades=[
            {
                "order_id": "near-open",
                "symbol": "NEARUSDT",
                "action": "OPEN",
                "side": "sell",
                "qty": 10.0,
                "status": "filled",
                "stop_loss": 6.0,
                "requested_stop_loss": 6.0,
                "stop_trigger_by": "mark",
                "stop_order_type": "market",
            }
        ],
    )
    current = JournalEntry(
        date="2026-11-15",
        run_at_utc="2026-11-15T01:06:00+00:00",
        signal_date="2026-11-13",
        equity=500.0,
        position_value=61.0,
        cash=439.0,
        day_pnl=0.0,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        positions=previous.positions,
        trades=[
            {
                "order_id": "near-open",
                "symbol": "NEARUSDT",
                "action": "OPEN",
                "side": "sell",
                "qty": 10.0,
                "status": "filled",
                "stop_loss": 6.0,
                "requested_stop_loss": 6.0,
                "stop_trigger_by": "mark",
                "stop_order_type": "market",
            }
        ],
    )
    upsert_entry(journal_path, previous)
    upsert_entry(journal_path, current)
    state_path = tmp_path / "state.json"
    active_event = {
        "signal_date": "2026-11-13",
        "targets_sha256": "target-a",
        "execution_hint": "2026-11-15T01:05:00+00:00",
        "applied_at": "2026-11-15T01:06:00+00:00",
        "equity_at_execution": 500.0,
        "target_weights": {"near": -0.1},
        "prices": {"near": 6.0},
        "target_quantities": {"NEARUSDT": 10.0},
        "position_status": "ok",
        "position_failures": [],
        "stopped_symbols": {},
    }
    state = {
        "account_fingerprint": "account-a",
        "last_key": "SPEC|2026-11-13|target-a|2026-11-15",
        "last_status": "ok",
        "last_run_at": "2026-11-15T01:06:00+00:00",
        "active_event": active_event,
        "stop_reconciliation_through": "2026-11-15T01:06:00+00:00",
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    args = execute_live_plan.parse_args(
        [
            "--live",
            "--reconcile-only",
            "--state-file",
            str(state_path),
            "--journal-file",
            str(journal_path),
            "--json-out",
            str(tmp_path / "reconcile.json"),
            "--capital-flows-file",
            str(tmp_path / "flows.csv"),
        ]
    )
    client = _ReconcileStopClient(trigger_ms)
    run_at = trigger.to_pydatetime() + pd.Timedelta(minutes=5)

    code = execute_live_plan._reconcile_live_stops_from_context(
        args,
        client=client,
        state=state,
        symbol_assets={"NEARUSDT": "near"},
        account_fp="account-a",
        run_at=run_at,
    )

    assert code == 0
    journal = load_journal(journal_path)
    row = journal.loc[journal["date"].astype(str) == "2026-11-15"].iloc[-1]
    trades = json.loads(row["trades"])
    close_trades = [trade for trade in trades if trade.get("reason") == "venue_strategy_stop"]
    assert len(close_trades) == 1
    assert close_trades[0]["order_id"] == "executed-stop-1"
    assert any(trade.get("order_id") == "near-open" for trade in trades)
    assert float(row["funding_total"]) == pytest.approx(0.006)
    reconciled_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert reconciled_state["active_event"]["stopped_symbols"]["NEARUSDT"]["order_id"] == "executed-stop-1"
    assert reconciled_state["stop_reconciliation_through"] == run_at.isoformat()

    second_code = execute_live_plan._reconcile_live_stops_from_context(
        args,
        client=client,
        state=reconciled_state,
        symbol_assets={"NEARUSDT": "near"},
        account_fp="account-a",
        run_at=run_at + pd.Timedelta(minutes=5),
    )

    assert second_code == 0
    journal = load_journal(journal_path)
    row = journal.loc[journal["date"].astype(str) == "2026-11-15"].iloc[-1]
    trades = json.loads(row["trades"])
    close_trades = [trade for trade in trades if trade.get("reason") == "venue_strategy_stop"]
    assert len(close_trades) == 1


def test_live_manifest_matches_the_pinned_ls104_spec() -> None:
    from atlas20.derivatives.live_chain import (
        LS104_G175_M090_FROZEN_CONFIG,
        LS104_G175_M090_MANIFEST_TOP_LEVEL,
        LS104_G175_M090_SPEC,
    )

    manifest = {
        "tracked_spec": LS104_G175_M090_SPEC,
        "frozen_config": LS104_G175_M090_FROZEN_CONFIG,
        **LS104_G175_M090_MANIFEST_TOP_LEVEL,
    }

    assert execute_live_plan._manifest_spec_issues(
        manifest,
        _manifest_args(
            spec=LS104_G175_M090_SPEC,
            max_gross_multiple=1.75,
            leverage=4.0,
            max_margin_utilization=0.90,
        ),
    ) == []


def test_live_manifest_rejects_ls104_with_a_two_x_venue_leverage() -> None:
    from atlas20.derivatives.live_chain import (
        LS104_G175_M090_FROZEN_CONFIG,
        LS104_G175_M090_MANIFEST_TOP_LEVEL,
        LS104_G175_M090_SPEC,
    )

    manifest = {
        "tracked_spec": LS104_G175_M090_SPEC,
        "frozen_config": LS104_G175_M090_FROZEN_CONFIG,
        **LS104_G175_M090_MANIFEST_TOP_LEVEL,
    }

    issues = execute_live_plan._manifest_spec_issues(
        manifest,
        _manifest_args(
            spec=LS104_G175_M090_SPEC,
            max_gross_multiple=1.75,
            leverage=2.0,
            max_margin_utilization=0.90,
        ),
    )

    assert any("leverage=2" in issue for issue in issues)


def test_bootstrap_track_can_apply_one_non_current_event_to_an_empty_track_only() -> None:
    assert execute_live_plan._event_plan_mode(
        fresh_target_event=False,
        active_event=None,
        bootstrap_track=True,
    ) == "fresh"
    assert execute_live_plan._event_plan_mode(
        fresh_target_event=False,
        active_event={"position_status": "ok"},
        bootstrap_track=True,
    ) == "maintain"


def test_bootstrap_track_rejects_reused_state_journal_or_unhashed_manifest() -> None:
    manifest = {"targets_sha256": "target-a"}
    assert execute_live_plan._bootstrap_track_issues(
        requested=True,
        state={},
        journal=pd.DataFrame(),
        manifest=manifest,
    ) == []
    assert execute_live_plan._bootstrap_track_issues(
        requested=True,
        state={"last_key": "old"},
        journal=pd.DataFrame(),
        manifest=manifest,
    )
    assert execute_live_plan._bootstrap_track_issues(
        requested=True,
        state={},
        journal=pd.DataFrame([{"date": "2026-11-14"}]),
        manifest=manifest,
    )
    assert execute_live_plan._bootstrap_track_issues(
        requested=True,
        state={},
        journal=pd.DataFrame(),
        manifest={},
    )
