"""Exposure schedules in the backtest engine.

An exposure schedule scales the book at each rebalance date. Between rebalances
the position drifts with price (no daily reset), which matches how a live
account behaves without constant rebalancing. Atlas20 is unlevered long-only
spot (AGENTS.md): gross exposure is capped at 1.0 and a higher cap is refused.
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
        gross_target_exposure=0.5,
    )

    # Signals take effect the day after the rebalance date, so day 2 earns half.
    assert result.equity_curve.iloc[1] == pytest.approx(100.0 * 1.05, rel=1e-9)
    # The position then drifts with price instead of resetting to 50% daily.
    assert result.equity_curve.iloc[2] == pytest.approx(100.0 * 1.05 * (1.0 + 0.55 / 1.05 * 0.10), rel=1e-9)


def test_exposure_schedule_overrides_constant_exposure() -> None:
    returns = _market([0.10, 0.10, 0.10])
    targets = {
        returns.index[0]: pd.Series({"bitcoin": 1.0}),
        returns.index[1]: pd.Series({"bitcoin": 1.0}),
    }
    schedule = {returns.index[0]: 0.5, returns.index[1]: 1.0}

    result = run_backtest(
        "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
        leverage_by_date=schedule,
    )

    # Day 2 uses the 50% scheduled for day 1; day 3 is fully invested.
    assert result.equity_curve.iloc[1] == pytest.approx(100.0 * 1.05, rel=1e-9)
    assert result.equity_curve.iloc[2] == pytest.approx(100.0 * 1.05 * 1.10, rel=1e-9)


def test_missing_schedule_date_defaults_to_constant_exposure() -> None:
    returns = _market([0.10, 0.10])
    targets = {returns.index[0]: pd.Series({"bitcoin": 1.0})}

    result = run_backtest(
        "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
        gross_target_exposure=0.5,
        leverage_by_date={},
    )

    assert result.equity_curve.iloc[1] == pytest.approx(100.0 * 1.05, rel=1e-9)


def test_exposure_above_one_is_capped_at_one_by_default() -> None:
    returns = _market([0.10, 0.10])
    targets = {returns.index[0]: pd.Series({"bitcoin": 1.0})}

    constant = run_backtest(
        "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
        gross_target_exposure=2.0,
    )
    scheduled = run_backtest(
        "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
        leverage_by_date={returns.index[0]: 99.0},
    )

    for result in (constant, scheduled):
        assert result.rebalance_targets.iloc[0].sum() == pytest.approx(1.0)
        assert result.equity_curve.iloc[1] == pytest.approx(100.0 * 1.10, rel=1e-9)


def test_a_leverage_cap_above_one_is_refused() -> None:
    returns = _market([0.10, 0.10])
    targets = {returns.index[0]: pd.Series({"bitcoin": 1.0})}

    with pytest.raises(ValueError, match="unlevered"):
        run_backtest(
            "t", returns, targets, pd.Series({"bitcoin": "x"}), _friction(), 100.0,
            max_gross_exposure=3.0,
        )
