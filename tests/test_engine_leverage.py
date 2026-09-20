"""Dynamic leverage support in the backtest engine.

A leverage schedule scales exposure at each rebalance date. Between rebalances
the position drifts with price (no daily leverage reset), which matches how a
live account behaves without constant rebalancing.
"""

from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import FrictionConfig


def _friction() -> FrictionConfig:
    return FrictionConfig(fee_bps=0.0, slippage_bps=0.0, max_weight_per_coin=1.0)


def _market(returns: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(returns), freq="D")
    return pd.DataFrame({"bitcoin": returns}, index=idx)


def test_constant_gross_exposure_applies_on_first_day() -> None:
    returns = _market([0.10, 0.10, 0.10])
    targets = {returns.index[0]: pd.Series({"bitcoin": 1.0})}

    result = run_backtest(
        "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
        gross_target_exposure=2.0,
    )

    # Signals take effect the day after the rebalance date, so day 2 earns 2x.
    assert result.equity_curve.iloc[1] == pytest.approx(100.0 * 1.20, rel=1e-9)
    # The position then drifts with price instead of resetting to 2x daily.
    assert result.equity_curve.iloc[2] == pytest.approx(100.0 * 1.20 * 1.1833333, rel=1e-6)


def test_leverage_schedule_overrides_constant_exposure() -> None:
    returns = _market([0.10, 0.10, 0.10])
    targets = {
        returns.index[0]: pd.Series({"bitcoin": 1.0}),
        returns.index[1]: pd.Series({"bitcoin": 1.0}),
    }
    schedule = {returns.index[0]: 2.0, returns.index[1]: 1.0}

    result = run_backtest(
        "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
        leverage_by_date=schedule,
    )

    # Day 2 uses the 2x scheduled for day 1; day 3 resets to 1x.
    assert result.equity_curve.iloc[1] == pytest.approx(100.0 * 1.20, rel=1e-9)
    assert result.equity_curve.iloc[2] == pytest.approx(100.0 * 1.20 * 1.10, rel=1e-6)


def test_missing_schedule_date_defaults_to_constant_exposure() -> None:
    returns = _market([0.10, 0.10])
    targets = {returns.index[0]: pd.Series({"bitcoin": 1.0})}

    result = run_backtest(
        "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
        gross_target_exposure=1.5,
        leverage_by_date={},
    )

    assert result.equity_curve.iloc[1] == pytest.approx(100.0 * 1.15, rel=1e-9)


def test_leverage_schedule_is_clamped_to_configured_bounds() -> None:
    returns = _market([0.10, 0.10])
    targets = {returns.index[0]: pd.Series({"bitcoin": 1.0})}

    result = run_backtest(
        "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
        leverage_by_date={returns.index[0]: 99.0},
        max_gross_exposure=3.0,
    )

    assert result.rebalance_targets.iloc[0].sum() == pytest.approx(3.0)
    assert result.equity_curve.iloc[1] == pytest.approx(100.0 * 1.30, rel=1e-9)
