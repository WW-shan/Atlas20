from __future__ import annotations

from pathlib import Path

import pandas as pd

from atlas20.derivatives.data import (
    load_binance_funding,
    load_bitget_funding,
    load_mark_candles,
)


def _symbol_map() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "coin_id": ["bitcoin", "near"],
            "bitget_symbol": ["BTCUSDT", "NEARUSDT"],
        }
    )


def test_load_mark_candles_maps_symbol_files_to_coin_ids(tmp_path: Path) -> None:
    candles = tmp_path / "candles"
    candles.mkdir()
    pd.DataFrame(
        {
            "open_time": ["2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00"],
            "open": [101.0, 100.0],
            "high": [102.0, 101.0],
            "low": [100.0, 99.0],
            "close": [101.5, 100.5],
            "volume": [1.0, 2.0],
            "quote_volume": [10.0, 20.0],
        }
    ).to_csv(candles / "BTCUSDT_mark.csv", index=False)

    loaded = load_mark_candles(tmp_path, _symbol_map())

    assert set(loaded) == {"bitcoin"}
    frame = loaded["bitcoin"]
    assert list(frame.columns) == ["open", "high", "low", "close"]
    assert frame.index.is_monotonic_increasing
    assert frame.iloc[0]["open"] == 100.0


def test_load_binance_funding_returns_wide_coin_columns(tmp_path: Path) -> None:
    pd.DataFrame(
        {
            "calc_time": [1767225600000, 1767254400000],
            "funding_interval_hours": [8, 8],
            "last_funding_rate": [0.0001, -0.0002],
        }
    ).to_csv(tmp_path / "bitcoin.csv", index=False)

    loaded = load_binance_funding(tmp_path, coins=["bitcoin", "near"])

    assert list(loaded.columns) == ["bitcoin"]
    assert loaded.index.is_monotonic_increasing
    assert loaded.iloc[0]["bitcoin"] == 0.0001


def test_load_bitget_funding_returns_wide_coin_columns(tmp_path: Path) -> None:
    funding = tmp_path / "funding"
    funding.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT", "BTCUSDT"],
            "funding_time": ["2026-01-02T00:00:00+00:00", "2026-01-02T08:00:00+00:00"],
            "funding_rate": [0.0001, 0.0002],
        }
    ).to_csv(funding / "bitcoin.csv", index=False)

    loaded = load_bitget_funding(tmp_path, _symbol_map(), coins=["bitcoin", "near"])

    assert list(loaded.columns) == ["bitcoin"]
    assert loaded.iloc[-1]["bitcoin"] == 0.0002
