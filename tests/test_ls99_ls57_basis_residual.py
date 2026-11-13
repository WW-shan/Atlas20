from __future__ import annotations

import pandas as pd
import pytest


def test_residual_scale_never_exceeds_gross_cap() -> None:
    from scripts.run_ls99_ls57_basis_residual import residual_scale

    gross = pd.Series([0.5, 1.2, 1.45, 1.5], index=pd.date_range("2024-01-01", periods=4, tz="UTC"))

    scale = residual_scale(gross, allocation=1.0, gross_cap=1.45, sleeve_gross=1.0)

    assert scale.tolist() == pytest.approx([0.95, 0.25, 0.0, 0.0])
    assert scale.loc[gross > 1.45].eq(0.0).all()


def test_combine_residual_basis_adds_scaled_return_and_charges_scale_change() -> None:
    from scripts.run_ls99_ls57_basis_residual import combine_residual_basis

    index = pd.date_range("2024-01-01", periods=3, tz="UTC")
    result = combine_residual_basis(
        ls57_returns=pd.Series([0.10, 0.00, 0.00], index=index),
        ls57_gross=pd.Series([0.45, 0.45, 1.45], index=index),
        basis_returns=pd.Series([0.01, 0.01, 0.01], index=index),
        allocation=1.0,
        gross_cap=1.45,
        sleeve_gross=1.0,
        scale_cost_bps=10.0,
    )

    assert result["scale"].tolist() == pytest.approx([1.0, 1.0, 0.0])
    assert result["combined_return"].iloc[0] == pytest.approx(0.109)
    assert result["combined_return"].iloc[1] == pytest.approx(0.01)
    assert result["combined_return"].iloc[2] == pytest.approx(-0.001)
    assert (result["combined_gross"] <= 1.45 + 1e-12).all()


def test_integration_classification_requires_all_primary_allocations() -> None:
    from scripts.run_ls99_ls57_basis_residual import classify_integration

    baseline = {
        "full_multiple": 68.0,
        "full_sharpe": 1.98,
        "full_max_drawdown": -0.398,
        "validation_multiple": 14.9,
        "validation_sharpe": 2.04,
    }
    rows = []
    for allocation in (0.25, 0.50, 1.00):
        rows.append(
            {
                "allocation": allocation,
                "basis_cost_bps": 10.0,
                "full_multiple": 70.0 + allocation,
                "full_sharpe": 2.00 + allocation,
                "full_max_drawdown": -0.397,
                "validation_multiple": 15.0,
                "validation_sharpe": 2.05,
            }
        )

    assert classify_integration(pd.DataFrame(rows), baseline) == "pass"

    rows[0]["full_multiple"] = 60.0
    assert classify_integration(pd.DataFrame(rows), baseline) == "partial"

    rows[2]["full_multiple"] = 60.0
    assert classify_integration(pd.DataFrame(rows), baseline) == "fail"


def test_combine_residual_basis_refuses_misaligned_returns() -> None:
    from scripts.run_ls99_ls57_basis_residual import combine_residual_basis

    index = pd.date_range("2024-01-01", periods=3, tz="UTC")
    with pytest.raises(ValueError, match="aligned"):
        combine_residual_basis(
            ls57_returns=pd.Series([0.0, 0.0, 0.0], index=index),
            ls57_gross=pd.Series([0.4, 0.4, 0.4], index=index),
            basis_returns=pd.Series([0.01, 0.01], index=index[:2]),
            allocation=1.0,
            gross_cap=1.45,
            sleeve_gross=1.0,
            scale_cost_bps=10.0,
        )


def test_classify_integration_fails_when_stress_100pct_is_below_baseline() -> None:
    from scripts.run_ls99_ls57_basis_residual import classify_integration

    baseline = {
        "full_multiple": 68.0,
        "full_sharpe": 1.98,
        "full_max_drawdown": -0.398,
        "validation_multiple": 14.9,
        "validation_sharpe": 2.04,
    }
    rows = []
    for allocation in (0.25, 0.50, 1.00):
        rows.append(
            {
                "allocation": allocation,
                "basis_cost_bps": 10.0,
                "full_multiple": 70.0 + allocation,
                "full_sharpe": 2.00 + allocation,
                "full_max_drawdown": -0.397,
                "validation_multiple": 15.0,
                "validation_sharpe": 2.05,
            }
        )
    rows.append(
        {
            "allocation": 1.00,
            "basis_cost_bps": 20.0,
            "full_multiple": 60.0,
            "full_sharpe": 1.80,
            "full_max_drawdown": -0.397,
            "validation_multiple": 14.0,
            "validation_sharpe": 1.90,
        }
    )

    assert classify_integration(pd.DataFrame(rows), baseline) == "fail"
