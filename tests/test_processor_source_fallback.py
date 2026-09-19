"""Processor-level tests for CryptoCompare -> Binance.US fallback."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from atlas20.config import load_config
from atlas20.data import processor


def _write_candidate(raw_dir: Path, coin_id: str, symbol: str) -> None:
    path = raw_dir / "coingecko" / "candidate_assets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "id": coin_id,
                    "symbol": symbol,
                    "name": symbol,
                    "market_cap": 1_000_000.0,
                    "market_cap_rank": 1,
                    "current_price": 100.0,
                    "total_volume": 10_000.0,
                }
            ]
        ),
        encoding="utf-8",
    )


def test_download_falls_back_to_binanceus_when_cryptocompare_fails(tmp_path, monkeypatch):
    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    config.start_date = "2024-01-01"
    config.end_date = "2024-01-05"
    raw_dir = tmp_path / "data" / "raw"
    _write_candidate(raw_dir, "bitcoin", "BTC")

    class _FailingCC:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def fetch_daily_history(self, symbol, force=False):
            raise RuntimeError("401 Client Error: Unauthorized")

    class _StubCG:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def fetch_top_markets(self, per_page, force=False):
            return pd.DataFrame()

        def fetch_markets_by_ids(self, coin_ids, force=False):
            return pd.DataFrame(
                [
                    {
                        "id": "bitcoin",
                        "symbol": "btc",
                        "name": "Bitcoin",
                        "market_cap": 1_000_000.0,
                        "market_cap_rank": 1,
                        "current_price": 100.0,
                        "total_volume": 10_000.0,
                    }
                ]
            )

        def fetch_coin_metadata(self, coin_id, force=False):
            return {}

        def fetch_daily_market_chart(self, coin_id, days, force=False):
            return pd.DataFrame()

    class _StubBinance:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def fetch_daily_history(self, symbol, force=False):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                    "close": [100.0, 101.0, 102.0],
                    "volume_usd": [1.0, 1.0, 1.0],
                }
            )

    monkeypatch.setattr(processor, "CryptoCompareClient", _FailingCC)
    monkeypatch.setattr(processor, "CoinGeckoClient", _StubCG)
    monkeypatch.setattr(processor, "BinanceUSClient", _StubBinance)

    result = processor.download_and_cache_raw_data(config)

    assert len(result) == 1, "asset must be retained via the fallback source"


def test_download_refreshes_current_source_even_when_legacy_cache_is_readable(tmp_path, monkeypatch):
    """A readable legacy cache must not stop the current source from refreshing."""
    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    raw_dir = tmp_path / "data" / "raw"
    _write_candidate(raw_dir, "bitcoin", "BTC")

    class _WorkingCC:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def fetch_daily_history(self, symbol, force=False):
            return pd.DataFrame(
                {"time": [1_700_000_000], "close": [100.0], "volumeto": [1000.0]}
            )

    class _StubCG:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def fetch_top_markets(self, per_page, force=False):
            return pd.DataFrame()

        def fetch_markets_by_ids(self, coin_ids, force=False):
            return pd.DataFrame(
                [
                    {
                        "id": "bitcoin",
                        "symbol": "btc",
                        "name": "Bitcoin",
                        "market_cap": 1_000_000.0,
                        "market_cap_rank": 1,
                        "current_price": 100.0,
                        "total_volume": 10_000.0,
                    }
                ]
            )

        def fetch_coin_metadata(self, coin_id, force=False):
            return {}

        def fetch_daily_market_chart(self, coin_id, days, force=False):
            return pd.DataFrame()

    calls: list[tuple[str, bool]] = []

    class _TrackingBinance:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def fetch_daily_history(self, symbol, force=False):
            calls.append((symbol, force))
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2024-01-01"]),
                    "close": [100.0],
                    "volume_usd": [1.0],
                }
            )

    monkeypatch.setattr(processor, "CryptoCompareClient", _WorkingCC)
    monkeypatch.setattr(processor, "CoinGeckoClient", _StubCG)
    monkeypatch.setattr(processor, "BinanceUSClient", _TrackingBinance)

    processor.download_and_cache_raw_data(config)

    assert calls == [("BTC", True)], "current source must be force-refreshed every download"
