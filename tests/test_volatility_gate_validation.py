from __future__ import annotations

from scripts.run_volatility_gate_validation import _volatility_gate_grid


def test_volatility_gate_grid_contains_expected_neighborhood() -> None:
    grid = _volatility_gate_grid()

    assert (30, 30, 1.5, 2) in grid
    assert (50, 30, 1.5, 2) in grid
    assert (30, 30, 2.0, 1) in grid
    assert (30, 30, 2.0, 5) in grid
    assert len(grid) == len(set(grid))
