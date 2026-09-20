"""Benchmarks must be live for the whole backtest window.

A benchmark is the yardstick every strategy is judged against. If it is only
entered at the first scheduled rebalance date (e.g. the first month-end), the
early days of the window are spent in cash and the benchmark silently
understates buy-and-hold returns - which flatters every strategy compared
against it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from atlas20.config import load_config
from atlas20.strategies.implementations import (
    StrategyDefinition,
    build_rebalance_targets,
)
from atlas20.universe.builder import MarketDataBundle


def _market(start: str, periods: int) -> MarketDataBundle:
    index = pd.date_range(start, periods=periods, freq="D")
    price = pd.DataFrame(
        {"bitcoin": np.linspace(100.0, 200.0, periods)}, index=index
    )
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1e6,
        volume=price * 0 + 1e9,
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame(
            {"symbol": ["BTC"], "name": ["Bitcoin"], "sector": ["Store of Value"]},
            index=["bitcoin"],
        ),
    )


def test_always_on_benchmark_is_live_from_the_first_day_of_the_window() -> None:
    config = load_config("config/base.yaml")
    config.project_root = None
    config.start_date = "2021-01-01"
    market = _market("2021-01-01", 90)
    strategy = StrategyDefinition(
        name="BTC_BH__always_on",
        family="benchmark",
        frequency="monthly",
        regime_mode="always_on",
        params={"coin_id": "bitcoin"},
    )

    targets, _ = build_rebalance_targets(
        strategy,
        market,
        pd.DataFrame(columns=["rebalance_date", "coin_id", "sector"]),
        pd.DataFrame(index=market.price.index),
        config,
    )

    first = market.price.index[0]
    assert first in targets, "the benchmark must be anchored on the window start"
    assert targets[first].to_dict() == {"bitcoin": 1.0}


def test_regime_filtered_benchmark_also_starts_at_the_window_open() -> None:
    config = load_config("config/base.yaml")
    config.project_root = None
    config.start_date = "2021-01-01"
    market = _market("2021-01-01", 90)
    strategy = StrategyDefinition(
        name="BTC_BH__bull_only",
        family="benchmark",
        frequency="monthly",
        regime_mode="bull_only",
        params={"coin_id": "bitcoin"},
    )
    regime = pd.DataFrame({"bull": True}, index=market.price.index)

    targets, _ = build_rebalance_targets(
        strategy,
        market,
        pd.DataFrame(columns=["rebalance_date", "coin_id", "sector"]),
        regime,
        config,
    )

    first = market.price.index[0]
    assert first in targets, "a trend-filtered benchmark still trades from day one"
    assert targets[first].to_dict() == {"bitcoin": 1.0}
