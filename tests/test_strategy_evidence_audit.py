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


def test_combine_tranches_uses_equal_weight_average() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    paths = {
        0: pd.Series([0.10, 0.00], index=index),
        10: pd.Series([0.00, 0.20], index=index),
        20: pd.Series([0.20, 0.40], index=index),
    }

    combined = _combine_tranches(paths, [0, 10, 20])

    assert combined.tolist() == pytest.approx([0.10, 0.20])


def test_metrics_from_returns_matches_compounded_multiple() -> None:
    returns = pd.Series([0.10, -0.10, 0.05])

    metrics = _metrics_from_returns(returns)

    assert metrics["multiple"] == pytest.approx(1.10 * 0.90 * 1.05)
    assert metrics["max_drawdown"] < 0.0
