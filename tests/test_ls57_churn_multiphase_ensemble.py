from __future__ import annotations

import pandas as pd
import pytest


def test_average_active_variant_weights_keeps_gross_at_most_one() -> None:
    from scripts.run_ls57_churn_multiphase_ensemble import average_active_variant_weights

    index = pd.DatetimeIndex(["2022-01-01", "2022-01-02"], tz="UTC")
    first = pd.DataFrame(
        {"bitcoin": [0.5, 0.0], "near": [-0.5, 0.0]},
        index=index,
    )
    second = pd.DataFrame(
        {"bitcoin": [0.0, 0.5], "near": [0.0, -0.5]},
        index=index,
    )

    weights, active = average_active_variant_weights({(3, 7): first, (7, 28): second})

    assert active.tolist() == [1, 1]
    assert weights.abs().sum(axis=1).tolist() == pytest.approx([1.0, 1.0])
    assert weights.loc[index[0], "near"] == pytest.approx(-0.5)
    assert weights.loc[index[1], "near"] == pytest.approx(-0.5)


def test_average_active_variant_weights_averages_overlap() -> None:
    from scripts.run_ls57_churn_multiphase_ensemble import average_active_variant_weights

    index = pd.DatetimeIndex(["2022-01-01"], tz="UTC")
    first = pd.DataFrame({"bitcoin": [0.5], "near": [-0.5]}, index=index)
    second = pd.DataFrame({"bitcoin": [0.25], "aave": [-0.25]}, index=index)

    weights, active = average_active_variant_weights({(3, 7): first, (7, 28): second})

    assert active.tolist() == [2]
    assert weights.loc[index[0], "bitcoin"] == pytest.approx(0.375)
    assert weights.loc[index[0], "near"] == pytest.approx(-0.25)
    assert weights.loc[index[0], "aave"] == pytest.approx(-0.125)
    assert weights.loc[index[0]].abs().sum() == pytest.approx(0.75)


def test_backtest_ensemble_charges_turnover_on_combined_book() -> None:
    from scripts.run_ls57_churn_multiphase_ensemble import backtest_ensemble_weights

    index = pd.DatetimeIndex(["2022-01-01", "2022-01-02", "2022-01-03"], tz="UTC")
    weights = pd.DataFrame(
        {"bitcoin": [0.0, 0.5, 0.5], "near": [0.0, -0.5, -0.5]},
        index=index,
    )
    returns = pd.DataFrame(
        {"bitcoin": [0.0, 0.01, 0.0], "near": [0.0, -0.02, 0.0]},
        index=index,
    )
    active = pd.Series([0, 1, 1], index=index)

    result = backtest_ensemble_weights(
        index=index,
        returns=returns,
        weights=weights,
        active_variant_count=active,
        cost_bps=20.0,
    )

    # Day 2 gross return = 0.5*1% + -0.5*(-2%) = 1.5%; entry cost = 2 bps.
    assert result.daily_returns.tolist() == pytest.approx([0.0, 0.013, -0.002])
    assert result.turnover.sum() == pytest.approx(2.0)


def test_short_asset_shares_sum_to_one() -> None:
    from scripts.run_ls57_churn_multiphase_ensemble import short_asset_shares

    index = pd.DatetimeIndex(["2022-01-01"], tz="UTC")
    weights = pd.DataFrame(
        {"bitcoin": [0.5], "near": [-0.25], "aave": [-0.25]},
        index=index,
    )

    shares = short_asset_shares(weights)

    assert shares["share"].sum() == pytest.approx(1.0)
    assert shares["asset"].tolist() == ["aave", "near"]


def test_robustness_diagnostics_reports_positive_increment() -> None:
    from scripts.run_ls57_churn_multiphase_ensemble import robustness_diagnostics

    index = pd.date_range("2022-01-01", periods=365 * 3, tz="UTC")
    baseline = pd.Series(0.0005, index=index)
    overlay = baseline + 0.0001

    summary, yearly, leave_one_out, rolling = robustness_diagnostics(
        overlay,
        baseline,
        scenario="normal",
    )

    assert summary["scenario"] == "normal"
    assert summary["years_outperforming"] == 3
    assert summary["mean_daily_excess"] == pytest.approx(0.0001)
    assert summary["bootstrap_probability_positive"] == pytest.approx(1.0)
    assert not yearly.empty
    assert not leave_one_out.empty
    assert not rolling.empty
