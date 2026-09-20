from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import FrictionConfig, load_config


def test_run_backtest_applies_rebalance_one_day_later_and_records_turnover() -> None:
    config = load_config("config/base.yaml")
    config.frictions.fee_bps = 0.0
    config.frictions.slippage_bps = 0.0
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"bitcoin": [0.0, 0.10, 0.0, 0.0], "ethereum": [0.0, 0.0, 0.0, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"bitcoin": 1.0})}
    sector_map = pd.Series({"bitcoin": "Store of Value", "ethereum": "Smart Contract Platform / L1"})

    result = run_backtest("test", returns, targets, sector_map, config.frictions, config.initial_capital)

    assert result.turnover.loc[dates[1]] == 1.0
    assert result.daily_returns.loc[dates[1]] == pytest.approx(0.10)
    assert result.equity_curve.loc[dates[1]] > result.equity_curve.loc[dates[0]]


def test_weights_stay_fully_invested_after_paying_trading_costs() -> None:
    """Regression: costs shrink capital, not holdings.

    The drift denominator used to be the *net* return, which divided by
    (1 - cost) as well and left the book implicitly levered by 1/(1-cost)
    after every rebalance. That compounded into an overstated return.
    """
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame(
        {"a": [0.0, 0.10, 0.0, 0.0], "b": [0.0, 0.0, 0.05, 0.0]},
        index=dates,
    )
    targets = {dates[0]: pd.Series({"a": 1.0}), dates[1]: pd.Series({"b": 1.0})}
    friction = FrictionConfig(fee_bps=10, slippage_bps=10, max_weight_per_coin=1.0)

    result = run_backtest(
        "t", returns, targets, pd.Series({"a": "x", "b": "x"}), friction, 100.0
    )

    # Fully invested whenever in the market, never implicitly levered.
    sums = result.weights.sum(axis=1)
    assert sums.tolist() == pytest.approx([0.0, 1.0, 1.0, 1.0])

    # Hand-derived: build at 20bp on day 1, rotate (turnover 2.0) on day 2.
    capital = 100.0 * (1.0 - 1.0 * 0.002) * 1.10
    capital = capital * (1.0 - 2.0 * 0.002) * 1.05
    assert result.equity_curve.iloc[-1] == pytest.approx(capital, rel=1e-12)
