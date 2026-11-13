from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_common_sample_refuses_missing_returns_without_zero_fill() -> None:
    from scripts.run_ls93_core_satellite_robustness import align_return_series

    index = pd.date_range("2022-01-01", periods=3, freq="D", tz="UTC")
    with pytest.raises(ValueError, match="missing|non-finite"):
        align_return_series(
            {
                "a": pd.Series([0.01, np.nan, 0.02], index=index),
                "b": pd.Series([0.02, 0.03, -0.01], index=index),
            }
        )


def test_sleeve_contributions_sum_to_portfolio_terminal_multiple() -> None:
    from scripts.run_ls93_core_satellite_robustness import sleeve_contributions

    index = pd.date_range("2022-01-01", periods=3, freq="D", tz="UTC")
    returns = pd.DataFrame(
        {
            "LS57": [0.0, 0.10, 0.0],
            "LS82_CARRY": [0.0, 0.0, 0.20],
        },
        index=index,
    )
    weights = {"LS57": 0.5, "LS82_CARRY": 0.5}

    contributions = sleeve_contributions(returns, weights=weights, baseline="LS57")

    expected = 0.5 * 1.10 + 0.5 * 1.20
    assert contributions["terminal_multiple_contribution"].sum() == pytest.approx(expected)
    assert contributions["wealth_share"].sum() == pytest.approx(1.0)
    assert contributions["excess_vs_baseline"].sum() == pytest.approx(expected - 1.10)


def test_integrity_check_rejects_a_portfolio_that_does_not_match_saved_returns() -> None:
    from scripts.run_ls93_core_satellite_robustness import assert_matches_saved_portfolio

    index = pd.date_range("2022-01-01", periods=3, freq="D", tz="UTC")
    computed = pd.Series([0.0, 0.01, 0.02], index=index)
    saved = pd.Series([0.0, 0.01, 0.03], index=index)

    with pytest.raises(ValueError, match="integrity"):
        assert_matches_saved_portfolio(computed, saved, label="LS92")


def test_evidence_classification_flags_cost_fragility() -> None:
    from scripts.run_ls93_core_satellite_robustness import classify_evidence

    summary = {
        13.0164: {
            "candidate_multiple": 68.0,
            "baseline_multiple": 65.0,
            "candidate_sharpe": 1.98,
            "baseline_sharpe": 1.96,
            "candidate_mdd": -0.383,
            "baseline_mdd": -0.389,
            "bootstrap_ci_2_5": 0.001,
            "years_outperforming": 4,
            "years_total": 5,
            "worst_leave_one_year_excess_multiple": -0.5,
        },
        20.0: {
            "candidate_multiple": 60.0,
            "baseline_multiple": 61.0,
            "candidate_sharpe": 1.92,
            "baseline_sharpe": 1.94,
            "candidate_mdd": -0.392,
            "baseline_mdd": -0.398,
            "bootstrap_ci_2_5": 0.0005,
            "years_outperforming": 3,
            "years_total": 5,
            "worst_leave_one_year_excess_multiple": -0.8,
        },
    }

    assert classify_evidence(summary, concentration=0.5) == "cost-fragile"


def test_evidence_classification_flags_sleeve_concentration() -> None:
    from scripts.run_ls93_core_satellite_robustness import classify_evidence

    summary = {
        cost: {
            "candidate_multiple": 68.0,
            "baseline_multiple": 65.0,
            "candidate_sharpe": 1.98,
            "baseline_sharpe": 1.96,
            "candidate_mdd": -0.383,
            "baseline_mdd": -0.389,
            "bootstrap_ci_2_5": 0.001,
            "years_outperforming": 4,
            "years_total": 5,
            "worst_leave_one_year_excess_multiple": 0.1,
        }
        for cost in (13.0164, 20.0)
    }

    assert classify_evidence(summary, concentration=0.85) == "sleeve-concentrated"


def test_evidence_reasons_expose_weak_increment_instead_of_only_a_label() -> None:
    from scripts.run_ls93_core_satellite_robustness import evidence_reasons

    summary = {
        13.0164: {
            "candidate_multiple": 68.0,
            "baseline_multiple": 65.0,
            "candidate_sharpe": 1.98,
            "baseline_sharpe": 1.96,
            "candidate_mdd": -0.383,
            "baseline_mdd": -0.389,
            "bootstrap_ci_2_5": -0.052,
            "years_outperforming": 3,
            "years_total": 5,
            "worst_leave_one_year_excess_multiple": -0.199,
        }
    }

    reasons = evidence_reasons(summary, concentration=0.607)

    assert any("13.0164bps" in line for line in reasons)
    assert any("bootstrap 2.5% -5.20%" in line for line in reasons)
    assert any("years 3/5" in line for line in reasons)
    assert any("incremental concentration 60.7%" in line for line in reasons)
