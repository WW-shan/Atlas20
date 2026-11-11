from __future__ import annotations

import pandas as pd
import pytest


def test_runner_freezes_riskbudget_candidate() -> None:
    from scripts.run_h5_riskbudget_funding_exit_short import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS9-H5-RISKBUDGET-FUNDING-EXIT"
    assert FROZEN_CONFIG["base_short_per_asset_weight_at_zero_long"] == 0.05
    assert FROZEN_CONFIG["funding_lookback_days"] == 7
    assert FROZEN_CONFIG["funding_rank_min"] == pytest.approx(2 / 3)
    assert FROZEN_CONFIG["funding_min_assets"] == 5
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
    assert FROZEN_CONFIG["max_total_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.00
    assert "short_risk_per_trade" not in FROZEN_CONFIG
    assert "short_per_asset_weight" not in FROZEN_CONFIG


def test_scale_schedule_uses_entry_date_unused_risk_once_per_position() -> None:
    from scripts.run_h5_riskbudget_funding_exit_short import _scale_schedule_by_long_gross

    index = pd.date_range("2022-01-01", periods=4, freq="D", tz="UTC")
    long_gross = pd.Series([0.9, 0.5, 0.9, 0.0], index=index)
    schedule = {
        index[0]: pd.Series({"a": 0.05}),
        index[1]: pd.Series({"a": 0.05, "b": 0.05}),
        index[2]: pd.Series({"a": 0.05, "b": 0.05}),
        index[3]: pd.Series({"b": 0.05}),
    }

    scaled = _scale_schedule_by_long_gross(schedule, long_gross)

    assert scaled[index[0]]["a"] == pytest.approx(0.005)
    assert scaled[index[1]]["a"] == pytest.approx(0.005)
    assert scaled[index[1]]["b"] == pytest.approx(0.025)
    assert scaled[index[2]]["a"] == pytest.approx(0.005)
    assert scaled[index[2]]["b"] == pytest.approx(0.025)
    assert scaled[index[3]]["b"] == pytest.approx(0.025)

def test_naive_h5_dates_are_normalized_before_riskbudget_scaling() -> None:
    from scripts.run_h5_riskbudget_funding_exit_short import (
        _long_gross_series,
        _scale_schedule_by_long_gross,
    )

    index = pd.date_range("2022-01-01", periods=2, freq="D")
    long_targets = {
        index[0]: pd.Series({"a": 1.0}),
        index[1]: pd.Series({"a": 0.25, "b": 0.25}),
    }
    utc_index = index.tz_localize("UTC")
    schedule = {
        utc_index[0]: pd.Series({"a": 0.05}),
        utc_index[1]: pd.Series({"b": 0.05}),
    }

    long_gross = _long_gross_series(long_targets, index)
    scaled = _scale_schedule_by_long_gross(schedule, long_gross)

    assert long_gross.index.tz is not None
    assert scaled[utc_index[0]].empty
    assert scaled[utc_index[1]]["b"] == pytest.approx(0.025)
