from __future__ import annotations

import pandas as pd
import pytest


def test_schedule_to_daily_weights_uses_next_day_and_forward_fills() -> None:
    from scripts.run_residual_momentum_screen import schedule_to_daily_weights

    index = pd.date_range("2026-01-01", periods=5, freq="D", tz="UTC")
    schedule = {
        index[1]: pd.Series({"A": 0.5, "B": -0.5}),
        index[3]: pd.Series({"C": 0.25}),
    }

    weights = schedule_to_daily_weights(index, schedule)

    assert weights.loc[index[0]].abs().sum() == pytest.approx(0.0)
    assert weights.loc[index[1]].abs().sum() == pytest.approx(0.0)
    assert weights.loc[index[2]].to_dict() == {"A": 0.5, "B": -0.5, "C": 0.0}
    assert weights.loc[index[3]].to_dict() == {"A": 0.5, "B": -0.5, "C": 0.0}
    assert weights.loc[index[4]].to_dict() == {"A": 0.0, "B": 0.0, "C": 0.25}


def test_backtest_schedule_charges_turnover_on_execution_day() -> None:
    from scripts.run_residual_momentum_screen import (
        backtest_schedule,
        schedule_to_daily_weights,
    )

    index = pd.date_range("2026-01-01", periods=4, freq="D", tz="UTC")
    returns = pd.DataFrame(
        {"A": [0.0, 0.0, 0.01, 0.0], "B": [0.0, 0.0, -0.01, 0.0]},
        index=index,
    )
    schedule = {index[1]: pd.Series({"A": 0.5, "B": -0.5})}

    result = backtest_schedule(index, returns, schedule, cost_bps=20.0)

    weights = schedule_to_daily_weights(index, schedule)
    assert result.weights.equals(weights)
    assert result.daily_returns.loc[index[2]] == pytest.approx(0.01 - 0.002)
    assert result.turnover.loc[index[2]] == pytest.approx(1.0)
    assert result.gross_exposure.max() == pytest.approx(1.0)


def test_asset_contribution_table_reports_signed_asset_pnl() -> None:
    from scripts.run_residual_momentum_screen import (
        asset_contribution_table,
        backtest_schedule,
    )

    index = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    returns = pd.DataFrame(
        {"A": [0.0, 0.10, 0.0], "B": [0.0, -0.10, 0.0]},
        index=index,
    )
    schedule = {index[0]: pd.Series({"A": 0.5, "B": -0.5})}

    result = backtest_schedule(index, returns, schedule, cost_bps=0.0)
    contributions = asset_contribution_table(result, returns)

    assert contributions.loc["A", "cumulative_contribution"] == pytest.approx(0.05)
    assert contributions.loc["B", "cumulative_contribution"] == pytest.approx(0.05)
    assert contributions["absolute_share"].sum() == pytest.approx(1.0)


def test_residual_momentum_screen_acceptance_requires_return_risk_and_breadth() -> None:
    from scripts.run_residual_momentum_screen import residual_momentum_acceptance

    passing = residual_momentum_acceptance(
        metrics_20={"multiple": 1.5, "sharpe": 1.0, "max_drawdown": -0.2},
        metrics_50={"multiple": 1.1, "sharpe": 0.7},
        positive_years=4,
        total_years=5,
        first_half_return=0.1,
        second_half_return=0.05,
    )
    assert all(passing.values())

    failing = residual_momentum_acceptance(
        metrics_20={"multiple": 0.9, "sharpe": 0.7, "max_drawdown": -0.45},
        metrics_50={"multiple": 0.8, "sharpe": 0.4},
        positive_years=3,
        total_years=5,
        first_half_return=0.1,
        second_half_return=-0.1,
    )
    assert not any(failing.values())
