from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_dsr_horizon import (
    PERIODS_PER_YEAR,
    ReturnShape,
    _raw_from_shape,
    _shape_from_raw,
    combined_shape,
    deflated_sharpe_probability,
    oos_days_for_significant_sharpe,
)
from scripts.run_phase_momentum_multiple_testing import _deflated_sharpe


def _returns(n: int = 800, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2022-01-01", periods=n, freq="D")
    # Exactly centred noise plus a fixed positive mean, so the sample Sharpe is
    # positive whatever the draw does to the raw mean.
    noise = rng.normal(0.0, 0.03, size=n)
    noise = noise - noise.mean()
    return pd.Series(noise + 0.002, index=index)


def test_moment_round_trip_recovers_the_shape() -> None:
    values = _returns().to_numpy(dtype=float)
    shape = _shape_from_raw(*np.array([(values**k).mean() for k in (1, 2, 3, 4)]))
    recovered = _shape_from_raw(*_raw_from_shape(shape))

    assert recovered.mean == pytest.approx(shape.mean, rel=1e-10)
    assert recovered.std == pytest.approx(shape.std, rel=1e-10)
    assert recovered.skew == pytest.approx(shape.skew, rel=1e-9)
    assert recovered.kurtosis == pytest.approx(shape.kurtosis, rel=1e-9)


def test_dsr_matches_the_project_formula() -> None:
    series = _returns()
    shape, n = combined_shape(series, oos_days=0, oos_annualized_sharpe=0.0)
    expected = _deflated_sharpe(series, expected_max_sharpe=0.05)["deflated_sharpe_probability"]

    # Population vs sample (ddof=1) moments differ slightly on a finite sample.
    assert deflated_sharpe_probability(shape, n, expected_max_sharpe_per_period=0.05) == pytest.approx(
        expected, abs=0.02
    )


def test_more_out_of_sample_days_at_the_same_sharpe_raise_the_dsr() -> None:
    series = _returns()
    in_sample_sharpe = (
        series.mean() / series.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)
    )
    short, n_short = combined_shape(series, oos_days=90, oos_annualized_sharpe=in_sample_sharpe)
    long, n_long = combined_shape(series, oos_days=730, oos_annualized_sharpe=in_sample_sharpe)

    assert n_long > n_short
    assert deflated_sharpe_probability(
        long, n_long, expected_max_sharpe_per_period=0.05
    ) > deflated_sharpe_probability(short, n_short, expected_max_sharpe_per_period=0.05)


def test_a_weaker_out_of_sample_sharpe_lowers_the_combined_sharpe() -> None:
    series = _returns()
    strong, _ = combined_shape(series, oos_days=365, oos_annualized_sharpe=2.0)
    weak, _ = combined_shape(series, oos_days=365, oos_annualized_sharpe=0.5)

    assert strong.mean / strong.std > weak.mean / weak.std


def test_oos_only_t_test_uses_the_standard_error_formula() -> None:
    # t = SR * sqrt(years) -> days = 365 * (critical / SR)^2
    assert oos_days_for_significant_sharpe(2.0, critical_value=1.6449) == pytest.approx(
        365.0 * (1.6449 / 2.0) ** 2
    )
    assert oos_days_for_significant_sharpe(0.0, critical_value=1.6449) == float("inf")
    # A stronger Sharpe needs fewer days.
    assert oos_days_for_significant_sharpe(2.0, critical_value=1.6449) < oos_days_for_significant_sharpe(
        1.0, critical_value=1.6449
    )


def test_zero_out_of_sample_days_returns_the_base_shape() -> None:
    series = _returns()
    shape, n = combined_shape(series, oos_days=0, oos_annualized_sharpe=5.0)

    assert n == len(series)
    assert shape.mean == pytest.approx(float(series.mean()), rel=1e-9)


def test_shape_helpers_reject_a_degenerate_series() -> None:
    with pytest.raises(ValueError):
        combined_shape(pd.Series([1.0, 2.0]), oos_days=10, oos_annualized_sharpe=1.0)


def test_flat_shape_has_no_deflated_sharpe() -> None:
    assert deflated_sharpe_probability(
        ReturnShape(0.0, 0.0, 0.0, 3.0), 100, expected_max_sharpe_per_period=0.0
    ) == 0.0
