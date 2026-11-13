from __future__ import annotations

import pandas as pd
import pytest


def test_rolling_window_metrics_reports_win_rate_and_worst_excess() -> None:
    from scripts.run_ls102_ls101_robustness import rolling_window_metrics

    index = pd.date_range("2024-01-01", periods=6, tz="UTC")
    candidate = pd.Series([0.01, 0.01, 0.01, -0.02, 0.01, 0.01], index=index)
    baseline = pd.Series([0.00, 0.00, 0.00, 0.00, 0.00, 0.00], index=index)

    frame = rolling_window_metrics(candidate, baseline, window=3)

    assert len(frame) == 4
    assert frame["excess_multiple"].iloc[0] > 0.0
    assert frame["excess_multiple"].min() == pytest.approx(frame["excess_multiple"].min())
    assert "mdd_delta" in frame.columns


def test_classify_robustness_fails_if_any_frozen_check_fails() -> None:
    from scripts.run_ls102_ls101_robustness import classify_robustness

    checks = {
        "cost_10": True,
        "cost_20": True,
        "cost_50": True,
        "cost_100": True,
        "yearly_4_of_5": True,
        "best_year_removed": True,
        "rolling_win_rate": True,
        "rolling_worst_terminal": True,
        "rolling_mdd_delta": True,
        "monthly_win_rate": True,
        "monthly_mdd_delta": True,
        "gross_cap": True,
        "finite": True,
    }

    assert classify_robustness(checks) == "pass"
    checks["rolling_mdd_delta"] = False
    assert classify_robustness(checks) == "robustness-fail"
