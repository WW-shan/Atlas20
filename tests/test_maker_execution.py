from __future__ import annotations

import pandas as pd
import pytest

from scripts.analyze_maker_execution import (
    simulate_trade,
    summarise,
    trade_direction,
)


def _bars() -> pd.DataFrame:
    index = pd.DatetimeIndex(["2026-01-02 03:00:00+00:00"])
    return pd.DataFrame(
        {
            "open": [100.0],
            "high": [101.0],
            "low": [98.0],
            "close": [99.0],
        },
        index=index,
    )


def _trade(side: str, action: str, *, notional: float = 100.0) -> dict[str, object]:
    return {
        "timestamp": "2026-01-02 03:00:00+00:00",
        "asset": "bitcoin",
        "side": side,
        "action": action,
        "notional": notional,
    }


def test_trade_direction_maps_signed_actions() -> None:
    assert trade_direction("long", "open") == "buy"
    assert trade_direction("long", "close") == "sell"
    assert trade_direction("short", "open") == "sell"
    assert trade_direction("short", "close") == "buy"
    assert trade_direction("long", "increase") == "buy"
    assert trade_direction("long", "reduce") == "sell"
    assert trade_direction("short", "increase") == "sell"
    assert trade_direction("short", "reduce") == "buy"


def test_maker_buy_fills_at_limit_and_improves_cost() -> None:
    result = simulate_trade(
        _trade("long", "open"),
        _bars(),
        offset_bps=5.0,
        timeout_bars=1,
        through_bps=1.0,
        maker_fee_bps=2.0,
        taker_fee_bps=20.0,
        baseline_fee_bps=20.0,
    )
    assert result["filled"] is True
    assert result["limit_price"] == pytest.approx(99.95)
    assert result["price_edge_bps"] == pytest.approx(5.0)
    assert result["effective_cost_bps"] == pytest.approx(-3.0)
    assert result["improvement_bps"] == pytest.approx(23.0)


def test_passive_sell_falls_back_when_price_never_trades_through() -> None:
    bars = _bars()
    bars.loc[:, "high"] = 100.04
    result = simulate_trade(
        _trade("short", "open"),
        bars,
        offset_bps=5.0,
        timeout_bars=1,
        through_bps=1.0,
        maker_fee_bps=2.0,
        taker_fee_bps=20.0,
        baseline_fee_bps=20.0,
    )
    assert result["filled"] is False
    assert result["fill_price"] == pytest.approx(99.0)
    assert result["effective_cost_bps"] > 20.0
    assert result["improvement_bps"] < 0.0


def test_summary_weights_by_notional() -> None:
    simulation = pd.DataFrame(
        {
            "available": [True, True],
            "notional": [90.0, 10.0],
            "filled": [True, False],
            "effective_cost_bps": [8.0, 100.0],
            "price_edge_bps": [5.0, -80.0],
            "improvement_bps": [12.0, -80.0],
        }
    )
    summary = summarise(
        simulation,
        total_notional=100.0,
        offset_bps=5.0,
        timeout_bars=2,
    )
    assert summary["coverage"] == pytest.approx(1.0)
    assert summary["notional_fill_rate"] == pytest.approx(0.9)
    assert summary["effective_cost_bps"] == pytest.approx(17.2)
    assert summary["improvement_bps"] == pytest.approx(2.8)


def test_invalid_assumptions_fail_closed() -> None:
    with pytest.raises(ValueError):
        trade_direction("flat", "open")
    with pytest.raises(ValueError):
        simulate_trade(
            _trade("long", "open"),
            _bars(),
            offset_bps=-1.0,
            timeout_bars=1,
            through_bps=0.0,
            maker_fee_bps=2.0,
            taker_fee_bps=20.0,
            baseline_fee_bps=20.0,
        )
