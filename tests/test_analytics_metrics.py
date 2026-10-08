"""Tests for the backtest performance analytics in ``atlas20.analytics.metrics``."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas20.analytics.metrics import compute_summary_metrics, performance_by_regime
from atlas20.backtest.engine import BacktestResult, run_backtest
from atlas20.config import FrictionConfig


def _result_from_returns(returns: pd.Series) -> BacktestResult:
    """A result built the way callers slice one: the equity starts after day one."""
    equity = (1.0 + returns).cumprod()
    return BacktestResult(
        name="slice",
        daily_returns=returns,
        equity_curve=equity,
        drawdown=equity / equity.cummax() - 1.0,
        weights=pd.DataFrame(index=returns.index),
        turnover=pd.Series(0.0, index=returns.index),
        holdings_count=pd.Series(1.0, index=returns.index),
        sector_exposure=pd.DataFrame(index=returns.index),
        rebalance_targets=pd.DataFrame(),
    )


def _engine_result() -> BacktestResult:
    index = pd.date_range("2024-01-01", periods=6, freq="D")
    returns = pd.DataFrame({"asset_a": [0.0, 0.05, -0.20, 0.10, -0.05, 0.03]}, index=index)
    return run_backtest(
        "engine",
        returns,
        {index[0]: pd.Series({"asset_a": 1.0})},
        pd.Series({"asset_a": "Other"}),
        FrictionConfig(fee_bps=10.0, slippage_bps=10.0, max_weight_per_coin=1.0),
        initial_capital=1_000.0,
    )


def test_total_return_keeps_the_first_day_of_a_sliced_result() -> None:
    """A per-year slice has no structural zero day to throw away.

    ``equity[-1] / equity[0]`` dropped the slice's first return: the ctrend
    champion's yearly table showed BTC 2024 at 111.5% instead of 121.1%.
    """
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.Series([0.10, -0.05, 0.20], index=index)

    metrics = compute_summary_metrics(_result_from_returns(returns))

    assert metrics["total_return"] == pytest.approx(1.10 * 0.95 * 1.20 - 1.0)


def test_total_return_and_drawdown_are_unchanged_for_engine_output() -> None:
    result = _engine_result()

    metrics = compute_summary_metrics(result)

    equity = result.equity_curve
    assert metrics["total_return"] == pytest.approx(equity.iloc[-1] / equity.iloc[0] - 1.0, abs=1e-12)
    assert metrics["max_drawdown"] == pytest.approx(float(result.drawdown.min()), abs=1e-12)


def test_max_drawdown_is_measured_from_the_starting_capital() -> None:
    """A loss on the first day is a drawdown from the capital put in.

    Without the starting 1.0 the running peak begins *after* the loss, so a
    ``[-10%, +5%]`` path reported no drawdown at all.
    """
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    returns = pd.Series([-0.10, 0.05], index=index)

    metrics = compute_summary_metrics(_result_from_returns(returns))

    assert metrics["max_drawdown"] == pytest.approx(-0.10)
    assert metrics["total_return"] == pytest.approx(0.90 * 1.05 - 1.0)


def test_sortino_uses_downside_deviation_not_the_demeaned_std_of_losses() -> None:
    """The denominator is sqrt(mean(min(r, 0)^2)), the target-semideviation at 0.

    ``std`` of ``min(r, 0)`` subtracts the mean of the clipped losses, which
    shrinks the denominator and overstated Sortino (BTC since 2021: 1.036 as
    coded against 0.908).
    """
    index = pd.date_range("2024-01-01", periods=6, freq="D")
    returns = pd.Series([0.0, 0.04, -0.02, 0.03, -0.02, 0.01], index=index)

    metrics = compute_summary_metrics(_result_from_returns(returns))

    downside_deviation = np.sqrt(np.mean(np.minimum(returns.to_numpy(), 0.0) ** 2)) * np.sqrt(365)
    assert metrics["sortino"] == pytest.approx(returns.mean() * 365 / downside_deviation)


def test_regime_performance_labels_each_return_with_the_previous_close() -> None:
    """Day t's return belongs to the regime known at t-1.

    The regime at close t already contains day t's return. Here the flag is
    literally "today's return was positive", so same-day labels put every
    up day in bull and every down day in non-bull by construction.
    """
    regime_index = pd.date_range("2023-12-31", periods=7, freq="D")
    returns = pd.Series([0.0, 0.10, -0.10, 0.10, -0.10, 0.10], index=regime_index[1:])
    bull = pd.Series(False, index=regime_index)
    bull.loc[returns.index] = (returns > 0).to_numpy()
    regime_frame = pd.DataFrame({"bull": bull})

    table = performance_by_regime({"strategy": _result_from_returns(returns)}, regime_frame)

    by_regime = table.set_index("regime")
    # Prior-day bull labels fall on 01-03 and 01-05, both -10% days.
    assert int(by_regime.loc["bull", "days"]) == 2
    assert float(by_regime.loc["bull", "annualized_return"]) < 0.0
    assert int(by_regime.loc["non_bull", "days"]) == 4
    assert float(by_regime.loc["non_bull", "annualized_return"]) > 0.0
