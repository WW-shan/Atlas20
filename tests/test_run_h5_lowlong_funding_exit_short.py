from __future__ import annotations

import pandas as pd
import pytest


def test_runner_freezes_lowlong_candidate() -> None:
    from scripts.run_h5_lowlong_funding_exit_short import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS8-H5-LOWLONG-FUNDING-EXIT"
    assert FROZEN_CONFIG["max_h5_long_gross_for_short"] == 0.50
    assert FROZEN_CONFIG["funding_lookback_days"] == 7
    assert FROZEN_CONFIG["funding_rank_min"] == pytest.approx(2 / 3)
    assert FROZEN_CONFIG["funding_min_assets"] == 5
    assert FROZEN_CONFIG["short_per_asset_weight"] == 0.025
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
    assert FROZEN_CONFIG["max_total_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.00


def test_long_gross_series_uses_latest_h5_target_without_lookahead() -> None:
    from scripts.run_h5_lowlong_funding_exit_short import _long_gross_series

    index = pd.date_range("2022-01-01", periods=5, freq="D", tz="UTC")
    targets = {
        index[0]: pd.Series({"a": 0.8, "b": 0.2}),
        index[2]: pd.Series({"a": 0.4}),
    }
    result = _long_gross_series(targets, index)

    assert result.tolist() == pytest.approx([1.0, 1.0, 0.4, 0.4, 0.4])

def test_long_gross_series_normalizes_naive_dates_to_utc() -> None:
    from scripts.run_h5_lowlong_funding_exit_short import _long_gross_series

    index = pd.date_range("2022-01-01", periods=2, freq="D")
    targets = {index[0]: pd.Series({"a": 1.0})}

    result = _long_gross_series(targets, index)

    assert result.index.tz is not None
    assert result.iloc[0] == pytest.approx(1.0)
