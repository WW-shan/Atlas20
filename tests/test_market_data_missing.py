"""Missing provider prices must not silently become flat returns."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.universe.builder import prepare_market_data


def test_prepare_market_data_preserves_terminal_missing_returns() -> None:
    """A feed that stops must not be forward-filled forever as zero returns."""
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    panel = pd.DataFrame(
        {
            "date": dates,
            "coin_id": ["a"] * len(dates),
            "price": [100.0, np.nan, np.nan, np.nan],
            "market_cap": [1_000.0] * len(dates),
            "volume_usd": [10_000.0] * len(dates),
        }
    )
    metadata = pd.DataFrame(
        {"symbol": ["A"], "name": ["Asset A"], "sector": ["Test"]},
        index=pd.Index(["a"], name="coin_id"),
    )

    market = prepare_market_data(panel, metadata, load_config("config/base.yaml"))

    assert pd.isna(market.raw_price.loc[dates[1], "a"])
    assert pd.isna(market.returns.loc[dates[1], "a"])
    assert pd.isna(market.returns.loc[dates[2], "a"])
    assert pd.isna(market.returns.loc[dates[3], "a"])


def test_prepare_market_data_carries_an_interior_gap_to_the_next_print() -> None:
    """A one-day CMC gap must not lose the cumulative move on resume."""
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    panel = pd.DataFrame(
        {
            "date": dates,
            "coin_id": ["a"] * len(dates),
            "price": [100.0, np.nan, 110.0, 121.0],
            "market_cap": [1_000.0] * len(dates),
            "volume_usd": [10_000.0] * len(dates),
        }
    )
    metadata = pd.DataFrame(
        {"symbol": ["A"], "name": ["Asset A"], "sector": ["Test"]},
        index=pd.Index(["a"], name="coin_id"),
    )

    market = prepare_market_data(panel, metadata, load_config("config/base.yaml"))

    assert market.returns.loc[dates[1], "a"] == 0.0
    assert market.returns.loc[dates[2], "a"] == pytest.approx(0.10)
    assert market.returns.loc[dates[3], "a"] == pytest.approx(0.10)
