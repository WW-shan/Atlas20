"""Fetch-order merge of overlapping provider cache windows.

Every provider client caches one file per requested window and the daily
refresh re-requests overlapping windows, so the same date is cached many times.
Which copy survives has to be a property of *when it was fetched*, never of how
an unstable sort happened to order equal dates.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from atlas20.data.cache_merge import fetch_ordered, merge_by_fetch_order


def _frame(days: list[str], close: float, **extra: object) -> pd.DataFrame:
    frame = pd.DataFrame({"date": pd.to_datetime(days), "close": close})
    for column, value in extra.items():
        frame[column] = value
    return frame


def test_fetch_ordered_sorts_by_modification_time_then_name(tmp_path: Path) -> None:
    newest = tmp_path / "1_1577836800_1790035200.json"
    oldest = tmp_path / "1_1789516800_1789948800.json"
    tie_b = tmp_path / "1_b.json"
    tie_a = tmp_path / "1_a.json"
    for path, fetched_at in ((newest, 300), (oldest, 100), (tie_b, 200), (tie_a, 200)):
        path.write_text("[]", encoding="utf-8")
        os.utime(path, (fetched_at, fetched_at))

    assert fetch_ordered([newest, tie_b, oldest, tie_a]) == [oldest, tie_a, tie_b, newest]


def test_newest_fetch_wins_on_every_duplicated_date() -> None:
    days = [day.date().isoformat() for day in pd.date_range("2025-08-21", periods=398, freq="D")]

    result = merge_by_fetch_order([_frame(days, 1.0), _frame(days, 2.0)], value_columns=["close"])

    assert len(result.frame) == 398
    assert (result.frame["close"] == 2.0).all()
    assert result.frame["date"].is_monotonic_increasing
    assert "_fetch_order" not in result.frame.columns
    assert result.duplicate_dates == 398
    assert result.conflicting_dates == 398
    assert result.examples and "close" in result.examples[0]


def test_dates_only_in_older_fetches_are_kept() -> None:
    older = _frame(["2024-01-01", "2024-01-02", "2024-01-03"], 1.0)
    newer = _frame(["2024-01-03", "2024-01-04"], 2.0)

    result = merge_by_fetch_order([older, newer], value_columns=["close"])

    assert result.frame["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
    ]
    assert result.frame["close"].tolist() == [1.0, 1.0, 2.0, 2.0]
    assert result.duplicate_dates == 1
    assert result.conflicting_dates == 1


def test_identical_duplicates_and_matching_missing_values_are_not_conflicts() -> None:
    days = ["2024-01-01", "2024-01-02"]
    older = _frame(days, 1.0, volume=np.nan)
    newer = _frame(days, 1.0, volume=np.nan)

    result = merge_by_fetch_order([older, newer], value_columns=["close", "volume"])

    assert result.duplicate_dates == 2
    assert result.conflicting_dates == 0
    assert result.examples == ()


def test_a_value_that_appears_or_disappears_between_fetches_is_a_conflict() -> None:
    older = _frame(["2024-01-01"], 1.0, volume=np.nan)
    newer = _frame(["2024-01-01"], 1.0, volume=5.0)

    result = merge_by_fetch_order([older, newer], value_columns=["close", "volume"])

    assert result.conflicting_dates == 1
    assert result.frame["volume"].tolist() == [5.0]


def test_empty_input_returns_an_empty_frame_with_the_requested_columns() -> None:
    result = merge_by_fetch_order([], value_columns=["close"], columns=["date", "close"])

    assert result.frame.empty
    assert list(result.frame.columns) == ["date", "close"]
    assert result.conflicting_dates == 0


def test_a_newest_fetch_that_drops_a_value_is_kept_and_reported() -> None:
    """The newest copy wins even when it carries a missing value; the merge must
    not quietly fall back to the last non-missing copy."""
    older = _frame(["2024-01-01"], 1.0, volume=5.0)
    middle = _frame(["2024-01-01"], 1.0, volume=5.0)
    newer = _frame(["2024-01-01"], 1.0, volume=np.nan)

    result = merge_by_fetch_order([older, middle, newer], value_columns=["close", "volume"])

    assert result.conflicting_dates == 1
    assert np.isnan(result.frame["volume"].iloc[0])
    assert "volume 5->nan" in result.examples[0]
