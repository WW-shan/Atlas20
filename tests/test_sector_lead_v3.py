"""Regression tests for the sector-lead v3 signal construction.

Two defects are pinned here:

1. ``sector_ret_21`` used to be a plain alias of ``sector_ret_30``.
2. The leader-coin score used a "relative to sector" term. Subtracting a
   per-sector constant from every member leaves the *within-sector* rank
   unchanged, so that term was mathematically identical to the raw 21-day
   momentum rank and silently doubled its weight.
"""

from __future__ import annotations

import pandas as pd

from atlas20.config import load_config
from atlas20.strategies.sector_lead_v3 import (
    LEADER_COIN_SCORE_WEIGHTS,
    build_sector_lead_v3_targets,
    compute_leader_coin_scores,
    compute_sector_lead_scores,
)
from atlas20.universe.builder import MarketDataBundle


DATES = pd.date_range("2024-01-01", periods=130, freq="D")


def _ramp(end: float, at_minus_22: float, at_minus_31: float) -> pd.Series:
    """Flat series that hits exact levels 21 and 30 days before the end."""
    series = pd.Series(100.0, index=DATES)
    series.iloc[-31] = at_minus_31
    series.iloc[-22] = at_minus_22
    series.iloc[-1] = end
    return series.interpolate()


def _toy_market() -> MarketDataBundle:
    # ret_21 ranking: dogecoin > litecoin-chain > litecoin
    # ret_30 ranking: litecoin > litecoin-chain > dogecoin
    price = pd.DataFrame(
        {
            "bitcoin": _ramp(100.0, 100.0, 100.0),
            "dogecoin": _ramp(100.0, 100.0 / 1.5, 100.0 / 1.1),
            "litecoin": _ramp(100.0, 100.0 / 1.1, 100.0 / 1.5),
            "chainlink": _ramp(100.0, 100.0 / 1.3, 100.0 / 1.3),
        },
        index=DATES,
    )
    metadata = pd.DataFrame(
        {
            "sector": {
                "bitcoin": "Store of Value",
                "dogecoin": "Meme",
                "litecoin": "Payments",
                "chainlink": "Infrastructure",
            }
        }
    )
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=price * 0 + 1_000_000,
        history_count=price.notna().cumsum(),
        metadata=metadata,
    )


def _snapshot(market: MarketDataBundle) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "coin_id": list(market.price.columns),
            "sector": [market.metadata["sector"][c] for c in market.price.columns],
        }
    )


def test_sector_ret_21_is_a_real_21_day_return_not_an_alias() -> None:
    market = _toy_market()
    scores = compute_sector_lead_scores(
        market, DATES[-1], _snapshot(market), {30: 0.5, 60: 0.3, 90: 0.2}
    )

    assert not scores["sector_ret_21"].equals(scores["sector_ret_30"])
    # Meme wins on 21 days, Payments wins on 30 days.
    assert scores.loc["Meme", "sector_ret_21"] > scores.loc["Payments", "sector_ret_21"]
    assert scores.loc["Payments", "sector_ret_30"] > scores.loc["Meme", "sector_ret_30"]


def test_sector_score_terms_are_not_duplicate_ranks() -> None:
    market = _toy_market()
    scores = compute_sector_lead_scores(
        market, DATES[-1], _snapshot(market), {30: 0.5, 60: 0.3, 90: 0.2}
    )

    rank_30 = scores["sector_rel_btc_30"].rank(pct=True)
    rank_21 = scores["sector_ret_21"].rank(pct=True)
    assert not rank_30.equals(rank_21)


def test_leader_coin_score_uses_a_short_horizon_term() -> None:
    """The third leader term must be a genuinely distinct signal."""
    assert "ret_7_rank" in LEADER_COIN_SCORE_WEIGHTS
    assert "rel_sector_21_rank" not in LEADER_COIN_SCORE_WEIGHTS

    # Two coins with identical 30/60/90-day and 21-day returns, and identical
    # distance from their 90-day high. Only the last 7 days differ.
    price = pd.DataFrame(index=DATES)
    price["bitcoin"] = 100.0
    surge = pd.Series(100.0, index=DATES)
    surge.iloc[-8] = 80.0
    price["dogecoin"] = surge.interpolate()
    price["litecoin"] = 100.0
    market = MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=price * 0 + 1_000_000,
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame({"sector": {"bitcoin": "SoV", "dogecoin": "Meme", "litecoin": "Payments"}}),
    )

    scores = compute_leader_coin_scores(
        market, DATES[-1], ["dogecoin", "litecoin"], {30: 0.5, 60: 0.3, 90: 0.2}
    )

    # Same momentum, same 21-day return, same proximity to high: the coin that
    # moved over the last week must win.
    assert scores.index[0] == "dogecoin"


def test_relative_to_sector_rank_is_mathematically_redundant() -> None:
    """Guard the reasoning behind the fix, not just its current shape."""
    raw = pd.Series({"a": 0.10, "b": 0.25, "c": -0.05, "d": 0.40})
    sector_mean = 0.13
    assert raw.rank(pct=True).equals((raw - sector_mean).rank(pct=True))


def test_bull_only_regime_goes_flat_outside_bull_market() -> None:
    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = str(DATES[0].date())
    config.rebalancing.frequencies["7D"] = "7D"
    rebalance_dates = pd.date_range(DATES[0], DATES[-1], freq="7D")
    universe = pd.DataFrame(
        [
            {
                "rebalance_date": date,
                "coin_id": coin,
                "universe_rank": rank,
                "price": 1.0,
                "market_cap": 10_000_000.0 / rank,
                "volume_usd": 1_000_000.0,
                "history_days": 120,
                "symbol": coin.upper(),
                "name": coin,
                "sector": market.metadata["sector"][coin],
            }
            for date in rebalance_dates
            for rank, coin in enumerate(market.price.columns, start=1)
        ]
    )
    # The 60/90-day momentum windows need history, so the bull day sits late
    # in the sample.
    bull_date = rebalance_dates[15]
    flat_date = rebalance_dates[17]
    regime = pd.DataFrame({"bull": False}, index=market.price.index)
    regime.loc[bull_date, "bull"] = True

    built = build_sector_lead_v3_targets(
        market, universe, regime, config, top_k=1, frequency="7D", regime_mode="bull_only"
    )

    assert built.targets[bull_date].sum() == 1.0
    assert built.targets[flat_date].empty


def test_targets_do_not_depend_on_future_prices() -> None:
    """A pick on day d must be reproducible from data up to day d alone.

    Rebuilding the strategy on a price matrix truncated at d must not change
    the pick on d. If it does, some signal is peeking at the future.
    """
    from atlas20.signals.regime import build_regime_frame

    market = _toy_market()
    config = load_config("config/base.yaml")
    config.start_date = str(DATES[0].date())
    config.rebalancing.frequencies["7D"] = "7D"
    config.regime.btc_ma_window = 5
    config.regime.tracked_total_mcap_ma_window = 5
    rebalance_dates = pd.date_range(DATES[0], DATES[-1], freq="7D")
    universe = pd.DataFrame(
        [
            {
                "rebalance_date": date,
                "coin_id": coin,
                "universe_rank": rank,
                "price": 1.0,
                "market_cap": 10_000_000.0 / rank,
                "volume_usd": 1_000_000.0,
                "history_days": 120,
                "symbol": coin.upper(),
                "name": coin,
                "sector": market.metadata["sector"][coin],
            }
            for date in rebalance_dates
            for rank, coin in enumerate(market.price.columns, start=1)
        ]
    )

    regime = build_regime_frame(market.price, market.market_cap, config)
    full = build_sector_lead_v3_targets(
        market, universe, regime, config, top_k=1, frequency="7D", regime_mode="always_on"
    ).targets

    probe = rebalance_dates[15]
    truncated_price = market.price.loc[:probe]
    truncated = MarketDataBundle(
        raw_price=truncated_price,
        price=truncated_price,
        returns=truncated_price.pct_change().fillna(0.0),
        market_cap=market.market_cap.loc[:probe],
        volume=market.volume.loc[:probe],
        history_count=market.history_count.loc[:probe],
        metadata=market.metadata,
    )
    truncated_regime = build_regime_frame(truncated.price, truncated.market_cap, config)
    cut = build_sector_lead_v3_targets(
        truncated, universe, truncated_regime, config, top_k=1, frequency="7D", regime_mode="always_on"
    ).targets

    assert full[probe].to_dict() == cut[probe].to_dict()
    assert full[probe].sum() == 1.0
