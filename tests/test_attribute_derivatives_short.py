import pandas as pd
import pytest

from scripts.attribute_derivatives_short import attribute


def test_attribute_accepts_relative_floating_point_close_quantity() -> None:
    quantity = 1_000_000_000.0
    trades = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T03:00:00+00:00",
                "asset": "bitcoin",
                "side": "short",
                "action": "open",
                "quantity": quantity,
                "price": 100.0,
                "fee": 0.0,
                "reason": "rebalance",
            },
            {
                "timestamp": "2026-01-02T03:00:00+00:00",
                "asset": "bitcoin",
                "side": "short",
                "action": "close",
                "quantity": quantity + 1e-7,
                "price": 100.0,
                "fee": 0.0,
                "reason": "rebalance",
            },
        ]
    )
    funding = pd.DataFrame(columns=["timestamp", "asset", "amount"])
    equity_curve = pd.DataFrame(
        {"equity": [100.0, 100.0]},
        index=pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"]),
    )

    episodes, assets, summary = attribute(trades, funding, equity_curve)

    assert len(episodes) == 1
    assert episodes.loc[0, "reason"] == "rebalance"
    assert summary["episodes"] == 1
    assert assets.loc[0, "asset"] == "bitcoin"


def test_attribute_closes_short_position_on_liquidation_event() -> None:
    trades = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T03:00:00+00:00",
                "asset": "bitcoin",
                "side": "short",
                "action": "open",
                "quantity": 10.0,
                "price": 100.0,
                "fee": 0.0,
                "reason": "rebalance",
            }
        ]
    )
    funding = pd.DataFrame(columns=["timestamp", "asset", "amount"])
    liquidations = pd.DataFrame(
        [
            {
                "trigger_timestamp": "2026-01-02T10:00:00+00:00",
                "asset": "bitcoin",
                "side": "short",
                "execution_price": 120.0,
                "quantity": 10.0,
            }
        ]
    )
    equity_curve = pd.DataFrame(
        {"equity": [100.0, 80.0]},
        index=pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"]),
    )

    episodes, assets, summary = attribute(trades, funding, equity_curve, liquidations)

    assert len(episodes) == 1
    assert episodes.loc[0, "reason"] == "liquidation"
    assert episodes.loc[0, "net_pnl"] == pytest.approx(-200.0)
    assert summary["episodes"] == 1
    assert assets.loc[0, "asset"] == "bitcoin"
