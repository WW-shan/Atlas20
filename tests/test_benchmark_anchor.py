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
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import load_config
from atlas20.pipeline import _all_rebalance_dates
from atlas20.strategies.implementations import (
    StrategyDefinition,
    build_rebalance_targets,
)
from atlas20.universe.builder import MarketDataBundle, build_rebalance_universe, prepare_market_data


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


@pytest.mark.parametrize("start", ["2022-01-01", "2022-01-15", "2022-01-31"])
@pytest.mark.parametrize("monthly_only", [False, True])
def test_equal_weight_benchmark_captures_the_first_invested_day(start: str, monthly_only: bool) -> None:
    config = load_config("config/base.yaml")
    config.start_date, config.end_date = start, "2022-02-03"
    if monthly_only:
        config.rebalancing.frequencies = {"monthly": "month_end"}
    first = pd.Timestamp(start)
    coins = ["bitcoin", *[f"coin{number:02}" for number in range(1, 20)]]
    panel = pd.DataFrame([
        {"date": date, "coin_id": coin, "price": 100.0 if date <= first else 110.0,
         "market_cap": 1e12 - rank * 1e10, "volume_usd": 1e9}
        for date in pd.date_range("2021-10-01", config.end_date)
        for rank, coin in enumerate(coins)
    ])
    metadata = pd.DataFrame(
        {"symbol": [f"C{rank:02}" for rank in range(20)], "name": coins, "sector": "Other"},
        index=pd.Index(coins, name="coin_id"),
    )
    market = prepare_market_data(panel, metadata, config)
    universe = build_rebalance_universe(market, _all_rebalance_dates(market.price.index, config), config)
    friction = config.frictions.model_copy(update={
        "fee_bps": 0.0, "slippage_bps": 0.0,
        "max_weight_per_coin": 1.0, "max_weight_per_sector": 1.0,
    })
    final_navs = []
    for family in ("benchmark", "equal_weight"):
        strategy = StrategyDefinition(family, family, "monthly", "always_on", {"coin_id": "bitcoin"})
        targets, dates = build_rebalance_targets(strategy, market, universe, pd.DataFrame(), config)
        assert dates == sorted({first, pd.Timestamp("2022-01-31")})
        assert first in targets and not targets[first].empty
        if family == "equal_weight":
            assert targets[first].to_dict() == dict.fromkeys(coins, 0.05)
        result = run_backtest(family, market.returns.loc[start:config.end_date], targets, metadata["sector"], friction, 1.0)
        assert result.daily_returns.loc[first + pd.Timedelta(days=1)] == pytest.approx(0.10)
        final_navs.append(result.equity_curve.iloc[-1])
    assert final_navs == pytest.approx([1.1, 1.1])
