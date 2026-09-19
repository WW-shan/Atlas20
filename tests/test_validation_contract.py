"""Contract tests for the history normalization used by source blending."""

from __future__ import annotations

import pandas as pd
import pytest

from atlas20.data.validation import prepare_cryptocompare_history


def test_prepare_accepts_raw_cryptocompare_frame() -> None:
    raw = pd.DataFrame(
        {
            "time": [int(pd.Timestamp("2024-01-01").timestamp())],
            "close": [100.0],
            "volumeto": [500.0],
        }
    )

    result = prepare_cryptocompare_history(raw)

    assert list(result.columns) == ["date", "cc_price", "cc_volume_usd"]
    assert result["cc_price"].iloc[0] == pytest.approx(100.0)
    assert result["cc_volume_usd"].iloc[0] == pytest.approx(500.0)


def test_prepare_accepts_normalized_spliced_frame() -> None:
    normalized = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"]),
            "close": [100.0],
            "volumeto": [500.0],
        }
    )

    result = prepare_cryptocompare_history(normalized)

    assert list(result.columns) == ["date", "cc_price", "cc_volume_usd"]
    assert result["cc_price"].iloc[0] == pytest.approx(100.0)


def test_prepare_accepts_normalized_volume_usd_frame() -> None:
    normalized = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"]),
            "close": [100.0],
            "volume_usd": [500.0],
        }
    )

    result = prepare_cryptocompare_history(normalized)

    assert result["cc_volume_usd"].iloc[0] == pytest.approx(500.0)
