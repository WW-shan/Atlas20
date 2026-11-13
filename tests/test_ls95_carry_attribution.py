from __future__ import annotations

import pandas as pd
import pytest


def test_signed_position_frame_handles_open_reduce_and_short_close() -> None:
    from scripts.run_ls95_carry_attribution import signed_position_frame

    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    trades = pd.DataFrame(
        [
            {"timestamp": index[0], "asset": "btc", "side": "long", "action": "open", "quantity": 2.0},
            {"timestamp": index[1], "asset": "btc", "side": "long", "action": "reduce", "quantity": 1.0},
            {"timestamp": index[2], "asset": "eth", "side": "short", "action": "open", "quantity": 3.0},
            {"timestamp": index[3], "asset": "eth", "side": "short", "action": "close", "quantity": 3.0},
        ]
    )

    positions = signed_position_frame(trades, index=index, assets=["btc", "eth"])

    assert positions["btc"].tolist() == pytest.approx([2.0, 1.0, 1.0, 1.0])
    assert positions["eth"].tolist() == pytest.approx([0.0, 0.0, -3.0, 0.0])


def test_attribution_classification_flags_asset_concentration() -> None:
    from scripts.run_ls95_carry_attribution import classify_attribution

    asset = pd.DataFrame(
        {
            "asset": ["cardano", "dogecoin", "bitcoin"],
            "net_pnl": [0.20, -0.08, 0.02],
        }
    )
    year = pd.DataFrame({"year": [2023, 2024], "net_pnl": [0.08, 0.06]})
    side = pd.DataFrame({"side": ["long", "short"], "net_pnl": [0.12, 0.02]})

    label = classify_attribution(
        asset_summary=asset,
        year_summary=year,
        side_summary=side,
        validation_correlation=0.99,
    )

    assert label == "asset-concentrated"


def test_attribution_classification_is_inconclusive_when_engine_check_fails() -> None:
    from scripts.run_ls95_carry_attribution import classify_attribution

    asset = pd.DataFrame({"asset": ["a", "b"], "net_pnl": [0.06, 0.04]})
    year = pd.DataFrame({"year": [2023, 2024], "net_pnl": [0.05, 0.05]})
    side = pd.DataFrame({"side": ["long", "short"], "net_pnl": [0.05, 0.05]})

    label = classify_attribution(
        asset_summary=asset,
        year_summary=year,
        side_summary=side,
        validation_correlation=0.80,
    )

    assert label == "inconclusive"
