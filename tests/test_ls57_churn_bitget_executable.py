from __future__ import annotations

import pandas as pd
import pytest


def test_bitget_mark_availability_uses_recent_lookback() -> None:
    from scripts.run_ls57_churn_bitget_executable import bitget_mark_availability

    index = pd.date_range("2022-01-01", periods=5, tz="UTC")
    marks = {
        "near": pd.DataFrame(
            {"close": [1.0, 1.0]},
            index=pd.DatetimeIndex(["2022-01-01 12:00", "2022-01-03 12:00"], tz="UTC"),
        )
    }

    result = bitget_mark_availability(
        marks,
        index=index,
        assets=["near", "missing"],
        lookback_days=2,
    )

    assert result["near"].tolist() == [True, True, True, True, False]
    assert result["missing"].sum() == 0


def test_funding_availability_uses_recent_settlements() -> None:
    from scripts.run_ls57_churn_bitget_executable import funding_availability

    index = pd.date_range("2022-01-01", periods=4, tz="UTC")
    funding = pd.DataFrame(
        {"near": [0.0001, float("nan"), float("nan"), float("nan")]},
        index=index,
    )

    result = funding_availability(funding, lookback_days=2)

    assert result["near"].tolist() == [True, True, False, False]


def test_weighted_mask_coverage_uses_short_weights_only() -> None:
    from scripts.run_ls57_churn_bitget_executable import weighted_mask_coverage

    index = pd.DatetimeIndex(["2022-01-01", "2022-01-02"], tz="UTC")
    weights = pd.DataFrame(
        {"bitcoin": [0.5, 0.5], "near": [-0.25, -0.25], "aave": [-0.25, -0.25]},
        index=index,
    )
    mask = pd.DataFrame(
        {"bitcoin": [False, False], "near": [True, True], "aave": [True, False]},
        index=index,
    )

    assert weighted_mask_coverage(weights, mask) == pytest.approx(0.75)


def test_eligibility_audit_reports_mark_and_funding_coverage() -> None:
    from scripts.run_ls57_churn_bitget_executable import eligibility_audit

    index = pd.DatetimeIndex(["2022-01-01", "2022-01-02"], tz="UTC")
    weights = pd.DataFrame(
        {"bitcoin": [0.5, 0.5], "near": [-0.5, -0.5]},
        index=index,
    )
    marks = pd.DataFrame({"bitcoin": [False, False], "near": [True, False]}, index=index)
    funding = pd.DataFrame({"bitcoin": [False, False], "near": [True, True]}, index=index)

    audit = eligibility_audit(weights, marks, funding, index=index)
    row = audit.loc[audit["asset"] == "near"].iloc[0]

    assert row["mark_coverage"] == pytest.approx(0.5)
    assert row["funding_coverage"] == pytest.approx(1.0)
    assert row["strict_coverage"] == pytest.approx(0.5)


def test_coverage_breakdown_separates_original_and_rebuilt_coverage() -> None:
    from scripts.run_ls57_churn_bitget_executable import coverage_breakdown

    index = pd.DatetimeIndex(["2022-01-01", "2022-01-02"], tz="UTC")
    original_weights = pd.DataFrame(
        {"bitcoin": [0.5, 0.5], "near": [-0.5, -0.5], "missing": [-1.0, -1.0]},
        index=index,
    )
    rebuilt_weights = pd.DataFrame(
        {"bitcoin": [0.5, 0.5], "near": [-0.5, -0.5], "missing": [0.0, 0.0]},
        index=index,
    )
    marks = pd.DataFrame(
        {"bitcoin": [False, False], "near": [True, True], "missing": [False, False]},
        index=index,
    )
    funding = pd.DataFrame(
        {"bitcoin": [True, True], "near": [True, True], "missing": [False, False]},
        index=index,
    )

    coverage = coverage_breakdown(
        original_weights=original_weights,
        rebuilt_weights=rebuilt_weights,
        marks=marks,
        funding=funding,
    )

    assert coverage["original_strict_weighted_coverage"] == pytest.approx(1.0 / 3.0)
    assert coverage["rebuilt_strict_weighted_coverage"] == pytest.approx(1.0)
    assert coverage["rebuilt_funding_coverage"] == pytest.approx(1.0)
