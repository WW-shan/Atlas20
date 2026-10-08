from __future__ import annotations

import pandas as pd
import pytest

import scripts.probe_cmc_publication as probe


def _frame(last: str) -> pd.DataFrame:
    dates = pd.date_range(end=last, periods=3, freq="D")
    return pd.DataFrame({"date": dates, "close": [1.0, 2.0, 3.0]})


def test_select_sample_ids_is_largest_first_and_deterministic() -> None:
    candidates = [
        {"cmc_id": 3, "market_cap": 10.0},
        {"cmc_id": 1, "market_cap": 100.0},
        {"cmc_id": 2, "market_cap": 10.0},
        {"cmc_id": None, "market_cap": 999.0},
        {"market_cap": 500.0},
    ]
    assert probe.select_sample_ids(candidates, 3) == [1, 2, 3]
    # ties break on the CMC id, so the basket is stable run to run
    assert probe.select_sample_ids(candidates, 2) == [1, 2]


def test_select_sample_ids_rejects_empty_request() -> None:
    with pytest.raises(ValueError):
        probe.select_sample_ids([{"cmc_id": 1, "market_cap": 1.0}], 0)


def test_coverage_of_target_counts_only_reached_histories() -> None:
    histories = {
        1: _frame("2026-10-07"),
        2: _frame("2026-10-07"),
        3: _frame("2026-10-06"),
        4: pd.DataFrame(),
    }
    assert probe.coverage_of_target(histories, "2026-10-07") == (2, 4)
    assert probe.coverage_of_target(histories, pd.Timestamp("2026-10-06")) == (3, 4)


def test_coverage_of_target_normalises_timezone_aware_dates() -> None:
    frame = pd.DataFrame({"date": pd.to_datetime(["2026-10-07T00:00:00+00:00"])})
    assert probe.coverage_of_target({7: frame}, "2026-10-07") == (1, 1)


def test_last_row_date_is_none_for_empty_input() -> None:
    assert probe._last_row_date(None) is None
    assert probe._last_row_date(pd.DataFrame()) is None
