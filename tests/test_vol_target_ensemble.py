from __future__ import annotations

import pandas as pd

from scripts.run_vol_target_ensemble import _summary_row


def test_summary_row_reports_period_and_metrics() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.Series([0.0, 0.01, 0.01], index=index)

    row = _summary_row("ensemble", returns, "oos_2023_plus", 20.0)

    assert row["strategy"] == "ensemble"
    assert row["period"] == "oos_2023_plus"
    assert row["cost_bps"] == 20.0
    assert row["start"] == index[0]
    assert row["end"] == index[-1]
    assert row["days"] == 3
    assert row["multiple"] > 1.0
