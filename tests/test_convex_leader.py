from __future__ import annotations

import pandas as pd
import pytest

from atlas20.strategies.convex_leader import (
    CTREND_LITE_SCORE_FAMILIES,
    build_ctrend_lite_targets,
    compute_ctrend_lite_scores,
)
from atlas20.config import load_config
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


def _toy_universe(dates: pd.DatetimeIndex, coin_ids: list[str] | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    coin_ids = coin_ids or ["bitcoin", "ethereum", "solana", "chainlink"]
    for date in dates:
        for rank, coin_id in enumerate(coin_ids, start=1):
            rows.append(
                {
                    "rebalance_date": date,
                    "coin_id": coin_id,
                    "universe_rank": rank,
                    "price": 1.0,
                    "market_cap": 10_000_000 / rank,
                    "volume_usd": 1_000_000,
                    "history_days": 100,
                    "symbol": coin_id.upper(),
                    "name": coin_id,
                    "sector": "Layer1",
                }
            )
    return pd.DataFrame(rows)


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


def test_ctrend_lite_scores_require_usable_reference_asset_history() -> None:
    market = _toy_market()
    market.price.loc[market.price.index[-29]:, "ethereum"] = pd.NA
    date = market.price.index[-1]

    with pytest.raises(ValueError, match="bitcoin and ethereum"):
        compute_ctrend_lite_scores(
            market,
            date,
            ["bitcoin", "ethereum", "solana"],
            CTREND_LITE_SCORE_FAMILIES["ctrend_lite_balanced"],
            require_reference_assets=True,
        )


def test_build_ctrend_lite_targets_uses_planned_interface_and_can_exclude_btc() -> None:
    market = _toy_market()
    date = market.price.index[-1]
    universe = pd.DataFrame(
        {
            "rebalance_date": [date, date, date],
            "coin_id": ["bitcoin", "solana", "chainlink"],
            "sector": ["Store of Value", "Smart Contract Platform / L1", "Infrastructure"],
        }
    )
    config = load_config("config/base.yaml")
    config.start_date = str(date.date())
    config.rebalancing.frequencies["daily"] = "1D"

    result = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=2,
        frequency="daily",
        score_family="ctrend_lite_balanced",
        include_btc=False,
    )

    assert date in result.targets
    assert "bitcoin" not in result.targets[date].index
    assert not result.targets[date].empty


def test_build_ctrend_lite_targets_respects_top_n_and_weights() -> None:
    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    config.rebalancing.frequencies["7D"] = "7D"
    dates = pd.date_range("2024-03-01", periods=5, freq="7D")
    universe = _toy_universe(dates)

    result = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=2,
        frequency="7D",
        score_family="ctrend_lite_balanced",
    )

    first_target = next(target for target in result.targets.values() if not target.empty)
    assert first_target.sum() == pytest.approx(1.0)
    assert len(first_target) == 2
    assert sorted(first_target.tolist(), reverse=True) == [0.6, 0.4]
    assert {"rebalance_date", "coin_id", "coin_score", "score_family"}.issubset(
        result.selection_history.columns
    )


def test_build_ctrend_lite_targets_can_exclude_btc_from_leader_pool() -> None:
    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    config.rebalancing.frequencies["7D"] = "7D"
    dates = pd.date_range("2024-03-01", periods=5, freq="7D")
    universe = _toy_universe(dates)

    result = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=3,
        frequency="7D",
        score_family="ctrend_lite_balanced",
        include_btc=False,
    )

    assert all("bitcoin" not in target.index for target in result.targets.values())


def test_build_ctrend_lite_targets_allows_literal_frequency_without_config_entry() -> None:
    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    dates = pd.date_range("2024-03-01", periods=5, freq="7D")
    universe = _toy_universe(dates)

    result = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=2,
        frequency="7D",
        score_family="ctrend_lite_balanced",
    )

    assert any(not target.empty for target in result.targets.values())


def test_build_ctrend_lite_targets_uses_equal_weights_for_more_than_three_leaders() -> None:
    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    config.rebalancing.frequencies["7D"] = "7D"
    dates = pd.date_range("2024-03-01", periods=5, freq="7D")
    universe = _toy_universe(dates, ["bitcoin", "ethereum", "solana", "chainlink", "dogecoin"])

    result = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=5,
        frequency="7D",
        score_family="ctrend_lite_balanced",
    )

    first_target = next(target for target in result.targets.values() if not target.empty)
    assert len(first_target) == 5
    assert first_target.sum() == pytest.approx(1.0)
    assert first_target.tolist() == pytest.approx([0.2] * 5)


def test_build_ctrend_lite_targets_rejects_unknown_score_family() -> None:
    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = "2024-03-01"
    config.rebalancing.frequencies["7D"] = "7D"
    dates = pd.date_range("2024-03-01", periods=5, freq="7D")
    universe = _toy_universe(dates)

    with pytest.raises(ValueError, match="Unknown CTREND-lite score_family"):
        build_ctrend_lite_targets(
            market,
            universe,
            config,
            top_n=2,
            frequency="7D",
            score_family="missing",
        )
