from __future__ import annotations

import pandas as pd
import pytest

from atlas20.strategies.convex_leader import (
    CTREND_LITE_SCORE_FAMILIES,
    compute_ctrend_lite_scores,
)
from atlas20.universe.builder import MarketDataBundle


def _toy_market() -> MarketDataBundle:
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": [100 + i * 0.4 for i in range(100)],
            "ethereum": [80 + i * 0.2 for i in range(100)],
            "solana": [10 + i * 1.2 for i in range(100)],
            "chainlink": [20 + i * 0.15 for i in range(100)],
            "dogecoin": [5 + i * 0.05 for i in range(100)],
        },
        index=dates,
    )
    price.loc[dates[-8]:, "dogecoin"] = [7, 11, 16, 22, 31, 44, 58, 76]
    volume = pd.DataFrame(
        {
            "bitcoin": [1_000_000.0] * 100,
            "ethereum": [800_000.0] * 100,
            "solana": [500_000.0 + i * 20_000 for i in range(100)],
            "chainlink": [300_000.0] * 100,
            "dogecoin": [120_000.0 + i * 50_000 for i in range(100)],
        },
        index=dates,
    )
    metadata = pd.DataFrame(
        {
            "sector": {
                "bitcoin": "Store of Value",
                "ethereum": "Smart Contract Platform / L1",
                "solana": "Smart Contract Platform / L1",
                "chainlink": "Infrastructure",
                "dogecoin": "Meme",
            }
        }
    )
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=volume,
        history_count=price.notna().cumsum(),
        metadata=metadata,
    )


def test_ctrend_lite_scores_rank_structural_leader_above_slow_coin() -> None:
    market = _toy_market()
    date = market.price.index[-1]

    scores = compute_ctrend_lite_scores(
        market,
        date,
        ["bitcoin", "ethereum", "solana", "chainlink"],
        CTREND_LITE_SCORE_FAMILIES["ctrend_lite_balanced"],
    )

    assert scores.index[0] == "solana"
    assert scores.loc["solana"] > scores.loc["chainlink"]
    assert scores.index.is_unique


def test_ctrend_lite_overheat_penalty_reduces_one_window_spike() -> None:
    market = _toy_market()
    date = market.price.index[-1]

    scores = compute_ctrend_lite_scores(
        market,
        date,
        ["solana", "dogecoin"],
        CTREND_LITE_SCORE_FAMILIES["ctrend_lite_vol_adjusted"],
    )

    assert scores.loc["solana"] > scores.loc["dogecoin"]


def test_ctrend_lite_scores_drop_assets_with_no_usable_data() -> None:
    market = _toy_market()
    market.price["newcoin"] = pd.NA
    market.volume["newcoin"] = pd.NA
    date = market.price.index[-1]

    scores = compute_ctrend_lite_scores(
        market,
        date,
        ["solana", "newcoin"],
        CTREND_LITE_SCORE_FAMILIES["ctrend_lite_balanced"],
    )

    assert list(scores.index) == ["solana"]


def test_ctrend_lite_scores_drop_assets_with_no_usable_volume_data() -> None:
    market = _toy_market()
    market.price["drycoin"] = market.price["chainlink"] * 1.5
    market.volume["drycoin"] = pd.NA
    date = market.price.index[-1]

    scores = compute_ctrend_lite_scores(
        market,
        date,
        ["solana", "drycoin"],
        CTREND_LITE_SCORE_FAMILIES["ctrend_lite_balanced"],
    )

    assert list(scores.index) == ["solana"]


def test_ctrend_lite_scores_require_btc_and_eth_for_relative_strength() -> None:
    market = _toy_market()
    date = market.price.index[-1]

    with pytest.raises(ValueError, match="bitcoin and ethereum"):
        compute_ctrend_lite_scores(
            market,
            date,
            ["solana", "chainlink"],
            CTREND_LITE_SCORE_FAMILIES["ctrend_lite_balanced"],
            require_reference_assets=True,
        )
