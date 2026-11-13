from __future__ import annotations


def test_fullgross_acceptance_requires_ten_percent_gain_over_ls73() -> None:
    from scripts.run_top20_churn_fullgross import acceptance_checks

    row = {
        "discovery_sharpe_20": 1.0,
        "validation_sharpe_20": 1.0,
        "pre2022_multiple_20": 1.0,
        "full_multiple_20": 1.17,
        "full_multiple_50": 1.1,
        "full_sharpe_20": 1.0,
        "full_max_drawdown_20": -0.1,
    }
    assert all(acceptance_checks(row).values())

    row["full_multiple_20"] = 1.10
    assert acceptance_checks(row)["full_multiple_at_least_1_10x_ls73"] is False
