from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_strategy_evidence_audit import (
    _combine_tranches,
    _metrics_from_returns,
    _phase_offsets,
)


def test_phase_offsets_cover_the_cycle_without_duplicates() -> None:
    assert _phase_offsets(1, 7) == [7]
    assert _phase_offsets(3, 0) == [0, 7, 14]
    assert _phase_offsets(7, 0) == [0, 3, 6, 9, 12, 15, 18]
    assert _phase_offsets(21, 0) == list(range(21))


def test_phase_offsets_reject_invalid_counts() -> None:
    with pytest.raises(ValueError, match="positive"):
        _phase_offsets(0, 0)


def test_combine_tranches_holds_equal_initial_capital() -> None:
    # Incident: the basket was the mean of the tranches' daily returns, i.e.
    # re-equalised across tranches every day for free (21-tranche CTREND
    # basket at 20 bps: 5.44x that way, 5.29x with the tranches simply held).
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    paths = {
        0: pd.Series([0.10, 0.00], index=index),
        10: pd.Series([0.00, 0.20], index=index),
        20: pd.Series([0.20, 0.40], index=index),
    }

    combined = _combine_tranches(paths, [0, 10, 20])

    # Tranche equity 1.10/1.10, 1.00/1.20, 1.20/1.68: the basket is their mean.
    assert combined.tolist() == pytest.approx([0.10, (1.10 + 1.20 + 1.68) / 3 / 1.10 - 1.0])


def test_combine_tranches_refuses_misaligned_paths() -> None:
    # Averaging around a missing day would silently re-weight the basket.
    first = pd.Series([0.10, 0.00], index=pd.date_range("2024-01-01", periods=2, freq="D"))
    second = pd.Series([0.00, 0.20], index=pd.date_range("2024-01-02", periods=2, freq="D"))

    with pytest.raises(ValueError, match="missing"):
        _combine_tranches({0: first, 1: second}, [0, 1])


def test_metrics_from_returns_matches_compounded_multiple() -> None:
    returns = pd.Series([0.10, -0.10, 0.05])

    metrics = _metrics_from_returns(returns)

    assert metrics["multiple"] == pytest.approx(1.10 * 0.90 * 1.05)
    assert metrics["max_drawdown"] < 0.0


def test_metrics_from_returns_measures_drawdown_from_the_starting_capital() -> None:
    """A first-day loss is a drawdown: the running peak starts at the 1.0 put in."""
    metrics = _metrics_from_returns(pd.Series([-0.10, 0.05]))

    assert metrics["max_drawdown"] == pytest.approx(-0.10)
    assert metrics["multiple"] == pytest.approx(0.90 * 1.05)
    # CAGR still spans len - 1 periods (engine series start with a zero day).
    assert metrics["cagr"] == pytest.approx((0.90 * 1.05) ** 365 - 1.0)
