from __future__ import annotations

import json

import pandas as pd
import pytest

from atlas20.derivatives.execution import (
    AccountState,
    ContractSpec,
    build_execution_plan,
)
from scripts.replay_live_execution import (
    _LedgerState,
    _apply_plan_order,
    _compare,
    _fill_prices,
    _specs_from_instruments,
)


def _trade(**kwargs) -> pd.Series:
    base = {
        "timestamp": pd.Timestamp("2026-01-02 03:00", tz="UTC"),
        "asset": "near",
        "side": "long",
        "action": "open",
        "quantity": 10.0,
        "price": 2.0,
        "notional": 20.0,
        "fee": 0.04,
        "margin": 10.3,
        "reason": "rebalance",
    }
    base.update(kwargs)
    return pd.Series(base)


def test_ledger_state_open_increase_reduce_close() -> None:
    state = _LedgerState(initial_cash=1.0)
    state.apply(_trade())
    assert state.cash == pytest.approx(1.0 - 10.3 - 0.04)
    assert state.positions["near"]["size"] == 10.0
    assert state.positions["near"]["margin"] == pytest.approx(10.3)

    state.apply(_trade(action="increase", quantity=5.0, price=2.2, notional=11.0, fee=0.022, margin=5.665))
    entry = state.positions["near"]
    assert entry["size"] == 15.0
    assert entry["entry"] == pytest.approx((10.0 * 2.0 + 5.0 * 2.2) / 15.0)
    assert entry["margin"] == pytest.approx(10.3 + 5.665)

    state.apply(_trade(action="reduce", quantity=5.0, price=2.5, notional=12.5, fee=0.025, margin=5.3216666667))
    entry = state.positions["near"]
    assert entry["size"] == 10.0
    blended_entry = (10.0 * 2.0 + 5.0 * 2.2) / 15.0
    expected_cash = (
        1.0 - 10.3 - 0.04 - 5.665 - 0.022 + 5.3216666667 + 5.0 * (2.5 - blended_entry) - 0.025
    )
    assert state.cash == pytest.approx(expected_cash)

    state.apply(_trade(action="close", quantity=10.0, price=2.6, notional=26.0, fee=0.052, margin=10.6433333333))
    assert "near" not in state.positions


def test_snapshot_equity_matches_ledger_math() -> None:
    state = _LedgerState(initial_cash=1.0)
    state.apply(_trade())

    snapshot = state.snapshot({"near": 2.5})

    assert snapshot.equity == pytest.approx(1.0 - 10.3 - 0.04 + 10.3 + 10.0 * (2.5 - 2.0))
    assert snapshot.available_margin == pytest.approx(state.cash)
    position = snapshot.positions["near"]
    assert position.notional == pytest.approx(25.0)


def test_fill_prices_reads_the_trade_rows() -> None:
    timestamp = pd.Timestamp("2026-01-02 03:00", tz="UTC")
    trades = pd.DataFrame(
        [
            _trade(timestamp=timestamp),
            _trade(timestamp=timestamp, asset="sol", price=100.0),
            _trade(timestamp=timestamp + pd.Timedelta(hours=24), asset="near", price=2.4),
        ]
    )

    assert _fill_prices(trades, timestamp) == {"near": 2.0, "sol": 100.0}


def test_compare_flags_action_size_and_extra_orders() -> None:
    account = AccountState(equity=100.0, available_margin=100.0)
    plan = build_execution_plan(
        account,
        {"near": 0.5},
        {"near": ContractSpec(symbol="NEARUSDT")},
        {"near": 2.0},
        mirror_engine=True,
    )
    matches, mismatches = _compare(plan, pd.DataFrame([_trade(quantity=25.0)]), tolerance=1e-9)
    assert len(matches) == 1 and not mismatches

    matches, mismatches = _compare(plan, pd.DataFrame([_trade(quantity=24.0)]), tolerance=1e-9)
    assert not matches and mismatches[0]["issue"] == "size mismatch"

    matches, mismatches = _compare(plan, pd.DataFrame([_trade(asset="sol")]), tolerance=1e-9)
    issues = {row["issue"] for row in mismatches}
    assert issues == {"unexpected planned order", "missing planned order"}


def test_apply_plan_order_keeps_isolated_margin_consistent() -> None:
    state = _LedgerState(initial_cash=1000.0)
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": 0.5},
        {"near": ContractSpec(symbol="NEARUSDT")},
        {"near": 2.0},
    )
    for order in plan.orders:
        _apply_plan_order(state, order, margin_ratio=plan.target_margin_ratio, fee_rate=0.002)

    entry = state.positions["near"]
    assert entry["size"] == pytest.approx(250.0)
    assert entry["margin"] == pytest.approx(500.0 * plan.target_margin_ratio)
    assert state.cash == pytest.approx(1000.0 - 500.0 * plan.target_margin_ratio - 500.0 * 0.002)


def test_specs_from_instruments_keys_by_asset_id() -> None:
    symbol_map = pd.DataFrame(
        [{"coin_id": "near", "bitget_symbol": "NEARUSDT"}]
    )
    rows = [
        {
            "symbol": "NEARUSDT",
            "minOrderQty": "1",
            "quantityMultiplier": "1",
            "minOrderAmount": "5",
            "quantityPrecision": "0",
        }
    ]

    specs = _specs_from_instruments(rows, symbol_map)

    assert specs["near"].symbol == "NEARUSDT"
    assert specs["near"].min_order_usdt == 5.0


def test_plan_cli_loads_account_file_and_formats_message(tmp_path) -> None:
    from scripts.plan_live_execution import format_execution_plan, load_account_file

    payload = {
        "equity": 500.0,
        "available_margin": 300.0,
        "as_of": "2026-10-09T02:00:00Z",
        "positions": [
            {
                "asset": "near",
                "symbol": "NEARUSDT",
                "side": "long",
                "size": 100.0,
                "entry_price": 2.0,
                "mark_price": 2.1,
                "margin": 105.0,
            }
        ],
    }
    path = tmp_path / "account.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    account = load_account_file(path)

    assert account.equity == 500.0
    assert account.positions["near"].size == 100.0
    assert account.as_of == pd.Timestamp("2026-10-09T02:00:00Z")

    plan = build_execution_plan(
        account,
        {"near": 0.6},
        {"near": ContractSpec(symbol="NEARUSDT", min_order_qty=1.0, quantity_multiplier=1.0)},
        {"near": 2.1},
    )
    message = format_execution_plan(
        plan,
        signal_date=pd.Timestamp("2026-10-08", tz="UTC"),
        execution_hint=pd.Timestamp("2026-10-09 03:00", tz="UTC"),
    )

    assert "账户权益 500.00 USDT" in message
    assert "加仓 NEAR" in message
    assert "保证金调整" in message


def test_symbol_map_loader_requires_columns(tmp_path) -> None:
    from scripts.plan_live_execution import load_symbol_map

    path = tmp_path / "map.csv"
    path.write_text("coin_id,other\nnear,x\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="bitget_symbol"):
        load_symbol_map(path)
