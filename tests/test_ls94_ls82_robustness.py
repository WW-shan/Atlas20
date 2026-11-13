from __future__ import annotations


def test_ls82_classification_flags_year_concentration_when_bootstrap_crosses_zero() -> None:
    from scripts.run_ls94_ls82_robustness import classify_ls82_evidence

    summary = {
        cost: {
            "candidate_multiple": 70.0,
            "baseline_multiple": 65.0,
            "candidate_sharpe": 2.00,
            "baseline_sharpe": 1.96,
            "candidate_mdd": -0.37,
            "baseline_mdd": -0.39,
            "bootstrap_ci_2_5": -0.01,
            "years_outperforming": 4,
            "years_total": 5,
            "worst_leave_one_year_excess_multiple": -0.10,
        }
        for cost in (13.0164, 20.0)
    }

    label = classify_ls82_evidence(
        summary,
        pbo_by_cost={13.0164: 0.40, 20.0: 0.45},
        reality_p_by_cost={13.0164: 0.02, 20.0: 0.03},
    )

    assert label == "year-concentrated"


def test_ls82_classification_does_not_call_a_non_significant_excess_robust() -> None:
    from scripts.run_ls94_ls82_robustness import classify_ls82_evidence

    summary = {
        cost: {
            "candidate_multiple": 70.0,
            "baseline_multiple": 65.0,
            "candidate_sharpe": 2.00,
            "baseline_sharpe": 1.96,
            "candidate_mdd": -0.37,
            "baseline_mdd": -0.39,
            "bootstrap_ci_2_5": 0.01,
            "years_outperforming": 4,
            "years_total": 5,
            "worst_leave_one_year_excess_multiple": 0.10,
        }
        for cost in (13.0164, 20.0)
    }

    label = classify_ls82_evidence(
        summary,
        pbo_by_cost={13.0164: 0.40, 20.0: 0.45},
        reality_p_by_cost={13.0164: 0.20, 20.0: 0.30},
    )

    assert label == "inconclusive"
