from __future__ import annotations

import pandas as pd
import pytest

from scripts.download_deribit_dvol import parse_dvol_rows


def test_parse_dvol_rows_sorts_deduplicates_and_normalizes_utc_dates() -> None:
    rows = [
        [1_704_240_000_000, 50.0, 55.0, 49.0, 54.0],
        [1_704_153_600_000, 48.0, 51.0, 47.0, 50.0],
        [1_704_240_000_000, 54.0, 56.0, 53.0, 55.0],
    ]

    frame = parse_dvol_rows(rows)

    assert frame["date"].tolist() == [
        pd.Timestamp("2024-01-02T00:00:00Z"),
        pd.Timestamp("2024-01-03T00:00:00Z"),
    ]
    assert frame["close"].tolist() == [50.0, 55.0]


def test_parse_dvol_rows_rejects_missing_or_non_positive_ohlc() -> None:
    with pytest.raises(ValueError, match="missing or non-finite"):
        parse_dvol_rows([[1_704_153_600_000, 48.0, None, 47.0, 50.0]])

    with pytest.raises(ValueError, match="non-positive"):
        parse_dvol_rows([[1_704_153_600_000, 48.0, 51.0, 47.0, 0.0]])
