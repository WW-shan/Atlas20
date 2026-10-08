from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

import scripts.attribute_phase_momentum_assets as attribution


@dataclass
class _Stub:
    """The two engine fields the attribution reads."""

    weights: pd.DataFrame
    rebalance_targets: pd.DataFrame


def _stub() -> _Stub:
    index = pd.date_range("2022-01-01", periods=3, freq="D")
    weights = pd.DataFrame({"a": [0.0, 1.0, 1.0], "b": [0.0, 0.0, 0.0]}, index=index)
    targets = pd.DataFrame({"a": [1.0], "b": [0.0]}, index=[index[0]])
    return _Stub(weights=weights, rebalance_targets=targets)


def test_coin_contribution_matrix_credits_the_target_on_the_fill_day() -> None:
    index = pd.date_range("2022-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, 0.20], "b": [0.0, 0.0, 0.0]}, index=index)
    matrix = attribution.coin_contribution_matrix(_stub(), returns)
    totals = matrix.attrs["totals"]
    # day 0: nothing held yet; day 1: target from day 0 earns 10%; day 2: drifted book earns 20%
    assert matrix.loc[index[0], "a"] == pytest.approx(0.0)
    assert matrix.loc[index[1], "a"] == pytest.approx(0.10)
    assert matrix.loc[index[2], "a"] == pytest.approx(0.20)
    assert totals["a"] == pytest.approx(0.30)
    assert totals["b"] == pytest.approx(0.0)


def test_coin_contributions_is_the_column_sum_of_the_matrix() -> None:
    index = pd.date_range("2022-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, 0.20], "b": [0.0, 0.01, 0.0]}, index=index)
    matrix = attribution.coin_contribution_matrix(_stub(), returns)
    series = attribution.coin_contributions(_stub(), returns)
    pd.testing.assert_series_equal(series, matrix.sum(axis=0).rename("contribution"))


def test_counterfactual_multiple_removes_only_the_named_coins() -> None:
    index = pd.date_range("2022-01-01", periods=2, freq="D")
    portfolio = pd.Series([0.0, 0.10], index=index)
    matrix = pd.DataFrame({"a": [0.0, 0.06], "b": [0.0, 0.04]}, index=index)
    assert attribution.counterfactual_multiple(portfolio, matrix, ()) == pytest.approx(1.10)
    assert attribution.counterfactual_multiple(portfolio, matrix, ("a",)) == pytest.approx(1.04)
    assert attribution.counterfactual_multiple(portfolio, matrix, ("a", "b")) == pytest.approx(1.0)
    # a coin the position never held cannot change anything
    assert attribution.counterfactual_multiple(portfolio, matrix, ("zzz",)) == pytest.approx(1.10)


def test_summarise_shares_sum_to_one_and_sort_descending() -> None:
    frame = attribution.summarise(pd.Series({"a": 3.0, "b": 1.0, "c": -2.0}))
    assert list(frame.index) == ["a", "b", "c"]  # descending by contribution
    assert frame["contribution"].tolist() == pytest.approx([3.0, 1.0, -2.0])
    assert frame["share"].sum() == pytest.approx(1.0)


def test_cash_yield_multiple_pays_only_the_idle_share() -> None:
    index = pd.date_range("2022-01-01", periods=2, freq="D")
    returns = pd.Series([0.0, 0.0], index=index)
    gross = pd.Series([1.0, 0.0], index=index)  # fully invested on day 1, all cash on day 2
    # 365 days of 100% cash at 36.5%/yr would double; here only one day is idle
    assert attribution.cash_yield_multiple(returns, gross, annual_yield=0.0) == pytest.approx(1.0)
    assert attribution.cash_yield_multiple(returns, gross, annual_yield=0.365) == pytest.approx(1.001)
    # a fully invested book earns nothing extra at any rate
    assert attribution.cash_yield_multiple(
        pd.Series([0.10, -0.05], index=index), pd.Series([1.0, 1.0], index=index), annual_yield=1.0
    ) == pytest.approx(1.045)


def test_cash_yield_multiple_handles_a_missing_gross_row() -> None:
    index = pd.date_range("2022-01-01", periods=2, freq="D")
    returns = pd.Series([0.0, 0.0], index=index)
    gross = pd.Series([0.0], index=index[:1])
    # the missing row is treated as cash, never as negative exposure
    assert attribution.cash_yield_multiple(returns, gross, annual_yield=0.365) == pytest.approx(1.002)
