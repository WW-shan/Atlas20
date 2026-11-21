from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.audit_derivatives_monte_carlo import (
    _path_metrics,
    _simulate,
    _stationary_indices,
    _summary,
)


def test_stationary_indices_are_bounded_and_preserve_requested_length() -> None:
    rng = np.random.default_rng(7)

    indices = _stationary_indices(50, block_length=5, rng=rng)

    assert len(indices) == 50
    assert indices.min() >= 0
    assert indices.max() < 50


def test_equal_returns_have_a_deterministic_path_multiple() -> None:
    terminal, _cagr, _sharpe, drawdown = _path_metrics(
        np.full(365, 0.001, dtype=float)
    )

    assert terminal == pytest.approx(1.001**365)
    assert drawdown == pytest.approx(0.0)


def test_drawdown_starts_from_initial_capital() -> None:
    _terminal, _cagr, _sharpe, drawdown = _path_metrics(
        np.array([-0.1, 0.05], dtype=float)
    )

    assert drawdown == pytest.approx(-0.10)


def test_simulation_is_reproducible_for_a_fixed_seed() -> None:
    returns = pd.Series(
        np.linspace(-0.02, 0.02, 100),
        index=pd.date_range("2022-01-01", periods=100, freq="D", tz="UTC"),
    )

    first = _simulate(returns, block_length=5, draws=20, seed=11)
    second = _simulate(returns, block_length=5, draws=20, seed=11)

    pd.testing.assert_frame_equal(first, second)


def test_summary_reports_tail_probabilities_by_block() -> None:
    simulation = pd.DataFrame(
        {
            "terminal_multiple": [0.5, 2.0, 4.0],
            "cagr": [-0.1, 0.2, 0.5],
            "sharpe": [-1.0, 0.5, 2.0],
            "max_drawdown": [-0.7, -0.3, -0.1],
        }
    )

    summary = _summary(simulation, block_length=20, draws=3, seed=9)

    assert summary["block_length_days"] == 20
    assert summary["terminal_multiple"]["probability_below_1"] == pytest.approx(1 / 3)
    assert summary["terminal_multiple"]["probability_below_2x"] == pytest.approx(1 / 3)
    assert summary["max_drawdown"]["probability_worse_than_50pct"] == pytest.approx(1 / 3)
    assert summary["sharpe"]["probability_negative"] == pytest.approx(1 / 3)
