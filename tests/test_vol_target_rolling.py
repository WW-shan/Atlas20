from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_phase_invariant_vol_target import _rolling_window_summary


def test_rolling_window_summary_reports_worst_and_median() -> None:
    index = pd.date_range("2024-01-01", periods=10, freq="D")
    returns = pd.Series([0.01] * 10, index=index)

    summary = _rolling_window_summary(returns, window_days=5)

    assert summary["rolling_1y_worst_multiple"] == pytest.approx(1.01**5)
    assert summary["rolling_1y_median_multiple"] == pytest.approx(1.01**5)
    assert summary["rolling_1y_worst_drawdown"] == pytest.approx(0.0)
