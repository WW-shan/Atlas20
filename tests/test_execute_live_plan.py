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
