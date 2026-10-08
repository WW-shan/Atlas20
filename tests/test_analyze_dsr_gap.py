from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_dsr_gap import analyse, required_annualized_sharpe
from scripts.run_phase_momentum_multiple_testing import _deflated_sharpe, _expected_max_sharpe


def _returns(seed: int = 7, length: int = 900) -> pd.Series:
    rng = np.random.default_rng(seed)
    # A plausible crypto-return shape: fat tails around an exact positive mean.
    noise = rng.normal(0.0, 0.02, length)
    jumps = rng.random(length) < 0.02
    noise[jumps] *= 5.0
    draws = noise - noise.mean() + 0.0015
    return pd.Series(draws, index=pd.date_range("2022-01-01", periods=length, freq="D"))


def _write_inventory(tmp_path: Path, n_trials: int) -> Path:
    summary = tmp_path / "summary.json"
    summary.write_text(
        (
            '{"all_trials": {"n_trials": %d, "sharpe_std_per_period": 0.03, "periods_per_year": 365}, '
            '"top20_2022_trials": {"n_trials": %d, "sharpe_std_per_period": 0.016, "periods_per_year": 365}}'
            % (n_trials, n_trials)
        ),
        encoding="utf-8",
    )
    return summary


def _write_family(tmp_path: Path, sharpes: list[float]) -> Path:
    path = tmp_path / "candidate_sharpes.csv"
    pd.DataFrame({"annualized_sharpe": sharpes}).to_csv(path, index=False)
    return path


def test_required_sharpe_round_trips_to_the_target() -> None:
    returns = _returns()
    expected = _expected_max_sharpe(500, 0.016)

    required = required_annualized_sharpe(returns, expected_max_sharpe=expected)
    std = float(returns.std(ddof=1))
    shifted = returns - returns.mean() + required / np.sqrt(365.0) * std

    probability = _deflated_sharpe(shifted, expected_max_sharpe=expected)["deflated_sharpe_probability"]
    assert probability == pytest.approx(0.95, abs=1e-4)


def test_required_sharpe_is_above_the_observed_when_the_gate_fails() -> None:
    returns = _returns()
    expected = _expected_max_sharpe(6000, 0.016)
    observed = float(returns.mean() / returns.std(ddof=1) * np.sqrt(365.0))

    required = required_annualized_sharpe(returns, expected_max_sharpe=expected)

    assert _deflated_sharpe(returns, expected_max_sharpe=expected)["deflated_sharpe_probability"] < 0.95
    assert required > observed


def test_required_sharpe_reports_no_headroom_when_the_gate_already_passes() -> None:
    returns = _returns()
    # No penalty at all: the gate passes on the observed Sharpe.
    expected = _expected_max_sharpe(1, 0.016)
    observed = float(returns.mean() / returns.std(ddof=1) * np.sqrt(365.0))

    assert _deflated_sharpe(returns, expected_max_sharpe=expected)["deflated_sharpe_probability"] >= 0.95
    assert required_annualized_sharpe(returns, expected_max_sharpe=expected) == pytest.approx(observed)


def test_required_sharpe_rejects_a_flat_or_too_short_series() -> None:
    with pytest.raises(ValueError):
        required_annualized_sharpe(pd.Series([1.0, 2.0]), expected_max_sharpe=0.1)
    with pytest.raises(ValueError):
        required_annualized_sharpe(pd.Series([0.0] * 10), expected_max_sharpe=0.1)
    with pytest.raises(ValueError):
        required_annualized_sharpe(_returns(), expected_max_sharpe=0.1, target=0.0)


def test_analyse_prices_every_reported_scope(tmp_path: Path) -> None:
    returns = _returns()

    table = analyse(
        returns,
        trial_summary=_write_inventory(tmp_path, 6000),
        candidate_sharpes=_write_family(tmp_path, [1.6, 1.4, 1.2, 1.0]),
    )

    assert set(table["scope"]) == {"family", "all_trials", "top20_2022_trials"}
    assert table.set_index("scope").loc["family", "trial_count"] == 4
    assert (table["shortfall_ratio"] > 1.0).all()
    assert not table["clears_target"].any()
