from __future__ import annotations

import pandas as pd
import pytest


def test_restrict_targets_reweights_remaining_shorts_and_keeps_btc_flat() -> None:
    from scripts.run_ls57_churn_spot_btc_short_alt import restrict_targets_to_executable_shorts

    index = pd.DatetimeIndex(["2022-01-01", "2022-01-02"], tz="UTC")
    targets = pd.DataFrame(
        {
            "bitcoin": [0.5, 0.0],
            "aave": [-0.25, 0.0],
            "near": [-0.25, 0.0],
        },
        index=index,
    )
    available = pd.DataFrame(
        {
            "aave": [False, False],
            "near": [True, True],
        },
        index=index,
    )

    result = restrict_targets_to_executable_shorts(targets, available)

    assert result.loc[index[0], "bitcoin"] == pytest.approx(0.5)
    assert result.loc[index[0], "aave"] == pytest.approx(0.0)
    assert result.loc[index[0], "near"] == pytest.approx(-0.5)
    assert result.loc[index[0]].abs().sum() == pytest.approx(1.0)
    assert result.loc[index[1]].abs().sum() == pytest.approx(0.0)


def test_restrict_targets_skips_event_when_no_short_is_executable() -> None:
    from scripts.run_ls57_churn_spot_btc_short_alt import restrict_targets_to_executable_shorts

    index = pd.DatetimeIndex(["2022-01-01"], tz="UTC")
    targets = pd.DataFrame(
        {"bitcoin": [0.5], "aave": [-0.25], "near": [-0.25]},
        index=index,
    )
    available = pd.DataFrame({"aave": [False], "near": [False]}, index=index)

    result = restrict_targets_to_executable_shorts(targets, available)

    assert result.loc[index[0]].abs().sum() == pytest.approx(0.0)


def test_short_funding_ignores_long_btc_and_charges_alt_short() -> None:
    from scripts.run_ls57_churn_spot_btc_short_alt import _short_funding_return

    index = pd.DatetimeIndex(["2022-01-01", "2022-01-02"], tz="UTC")
    weights = pd.DataFrame(
        {"bitcoin": [0.5, 0.5], "near": [-0.5, -0.5]},
        index=index,
    )
    normal = pd.DataFrame(
        {"bitcoin": [0.01, 0.01], "near": [0.002, -0.001]},
        index=index,
    )
    adverse = pd.DataFrame(
        {"bitcoin": [0.01, 0.01], "near": [0.003, 0.002]},
        index=index,
    )

    result = _short_funding_return(weights, normal, adverse, multiplier=0)

    assert result.tolist() == pytest.approx([0.001, -0.0005])


def test_adverse_funding_charges_every_short_with_absolute_rate() -> None:
    from scripts.run_ls57_churn_spot_btc_short_alt import _short_funding_return

    index = pd.DatetimeIndex(["2022-01-01"], tz="UTC")
    weights = pd.DataFrame({"bitcoin": [0.5], "near": [-0.5]}, index=index)
    normal = pd.DataFrame({"bitcoin": [0.01], "near": [0.002]}, index=index)
    adverse = pd.DataFrame({"bitcoin": [0.01], "near": [0.003]}, index=index)

    result = _short_funding_return(weights, normal, adverse, multiplier=3)

    assert result.tolist() == pytest.approx([-0.0045])


def test_short_funding_coverage_only_counts_short_legs() -> None:
    from scripts.run_ls57_churn_spot_btc_short_alt import short_funding_coverage

    index = pd.DatetimeIndex(["2022-01-01"], tz="UTC")
    weights = pd.DataFrame({"bitcoin": [0.5], "near": [-0.5]}, index=index)
    funding = pd.DataFrame({"bitcoin": [float("nan")], "near": [0.001]}, index=index)

    assert short_funding_coverage(weights, funding) == pytest.approx(1.0)
