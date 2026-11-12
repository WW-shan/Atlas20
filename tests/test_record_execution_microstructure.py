from __future__ import annotations

import pandas as pd
import pytest

from atlas20.derivatives.orderbook import OrderBookLevel, OrderBookSnapshot
from scripts.record_execution_microstructure import (
    build_microstructure_rows,
    select_execution_legs,
)


def _book() -> OrderBookSnapshot:
    observed = pd.Timestamp("2026-11-13T01:05:00Z")
    return OrderBookSnapshot(
        symbol="XMRUSDT",
        bids=(OrderBookLevel(543.0, 0.2), OrderBookLevel(542.0, 2.0)),
        asks=(OrderBookLevel(544.0, 0.2), OrderBookLevel(545.0, 2.0)),
        observed_at=observed,
        received_at=observed,
    )


def test_select_execution_legs_sizes_changes_from_real_equity() -> None:
    book = pd.DataFrame(
        [
            {
                "asset": "monero",
                "target_weight": 0.25,
                "change_weight": 0.05,
                "action": "BUY",
            },
            {
                "asset": "near",
                "target_weight": 0.0,
                "change_weight": -0.10,
                "action": "CLOSE",
            },
            {
                "asset": "bitcoin",
                "target_weight": 0.0,
                "change_weight": 0.0,
                "action": "HOLD",
            },
        ]
    )

    legs = select_execution_legs(
        book,
        {"monero": "XMRUSDT", "near": "NEARUSDT", "bitcoin": "BTCUSDT"},
        equity=500.0,
    )

    assert [leg["asset"] for leg in legs] == ["monero", "near"]
    assert legs[0]["side"] == "buy"
    assert legs[0]["change_notional"] == pytest.approx(25.0)
    assert legs[1]["side"] == "sell"
    assert legs[1]["change_notional"] == pytest.approx(-50.0)


def test_build_microstructure_rows_walks_visible_depth() -> None:
    legs = [
        {
            "asset": "monero",
            "symbol": "XMRUSDT",
            "side": "sell",
            "target_weight": 0.0,
            "change_weight": -0.46875,
            "change_notional": -234.375,
        }
    ]

    rows = build_microstructure_rows(
        legs,
        {"XMRUSDT": _book()},
        observation_index=3,
        execution_hint=pd.Timestamp("2026-11-13T03:00:00Z"),
    )

    row = rows[0]
    assert row["observation_index"] == 3
    assert row["requested_notional"] == pytest.approx(234.375)
    assert row["filled_notional"] == pytest.approx(234.375)
    assert row["levels_consumed"] == 2
    assert row["fill_ratio"] == pytest.approx(1.0)
    assert row["impact_bps"] == pytest.approx(9.891313515709463)
