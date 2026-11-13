from __future__ import annotations

import pandas as pd
import pytest


def test_no_rebalance_ensemble_uses_compounded_subaccounts() -> None:
    from scripts.run_ls90_multi_strategy_ensemble import combine_no_rebalance

    index = pd.date_range("2022-01-01", periods=3, freq="1D", tz="UTC")
    returns = pd.DataFrame(
        {"a": [0.0, 0.10, 0.0], "b": [0.0, 0.0, 0.10]},
        index=index,
    )

    portfolio = combine_no_rebalance(returns, weights={"a": 0.5, "b": 0.5})

    assert portfolio.iloc[0] == pytest.approx(0.0)
    assert portfolio.iloc[1] == pytest.approx(0.05)
    assert portfolio.iloc[2] == pytest.approx(1.10 / 1.05 - 1.0)


def test_no_rebalance_ensemble_rejects_missing_weights() -> None:
    from scripts.run_ls90_multi_strategy_ensemble import combine_no_rebalance

    returns = pd.DataFrame({"a": [0.0, 0.01]}, index=pd.date_range("2022-01-01", periods=2, tz="UTC"))
    with pytest.raises(ValueError, match="weights"):
        combine_no_rebalance(returns, weights={"a": 1.0, "b": 0.0})


def test_report_uses_actual_weights_and_cost_assumption() -> None:
    from scripts.run_ls90_multi_strategy_ensemble import _report

    summary = pd.DataFrame(
        [
            {
                "portfolio": "LS57",
                "cost_bps": 13.0164,
                "full_multiple": 65.6712,
                "full_sharpe": 1.9638,
                "full_max_drawdown": -0.3896,
                "validation_multiple": 14.9011,
                "validation_sharpe": 2.0925,
            },
            {
                "portfolio": "LS92",
                "cost_bps": 13.0164,
                "full_multiple": 68.7216,
                "full_sharpe": 1.9798,
                "full_max_drawdown": -0.3837,
                "validation_multiple": 15.4108,
                "validation_sharpe": 2.1078,
            },
        ]
    )
    weights = {
        "LS57": 0.50,
        "LS82_CARRY": 0.25,
        "LS88_LONG_CARRY": 0.25,
        "LS89_MA21": 0.0,
    }

    report = _report(
        summary,
        summary.iloc[:1],
        pd.DataFrame({"LS57": [1.0], "LS92": [0.9]}, index=["LS57"]),
        trial_id="LS92",
        weights=weights,
        cost_bps=13.0164,
    )

    assert "Capital weights: 50.0% LS57 + 25.0% LS82_CARRY + 25.0% LS88_LONG_CARRY + 0.0% LS89_MA21" in report
    assert "Cost assumption: 13.0164bps" in report
    assert "Subaccounts (13.0164bps)" in report
    assert "Return correlations (13.0164bps)" in report
    assert "13.0164bps LS57:" in report
