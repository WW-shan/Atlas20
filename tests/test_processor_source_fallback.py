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


def test_processed_dataset_includes_assets_without_legacy_cache(tmp_path, monkeypatch):
    """Assets listed after the CryptoCompare shutdown have no legacy file."""
    from atlas20.data import validation

    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    raw_dir = tmp_path / "data" / "raw"
    _write_candidate(raw_dir, "newcoin", "NEW")
    # Binance.US history only; no cryptocompare/histoday/NEW.json exists.
    klines = raw_dir / "binanceus" / "klines" / "NEW.json"
    klines.parent.mkdir(parents=True, exist_ok=True)
    klines.write_text(
        json.dumps(
            [
                [int(pd.Timestamp(d).timestamp() * 1000), "0", "0", "0", str(p), "0", 0, "1000", 0, "0", "0", "0"]
                for d, p in [
                    ("2025-01-01", 10.0),
                    ("2025-01-02", 11.0),
                    ("2025-01-03", 12.0),
                ]
            ]
        ),
        encoding="utf-8",
    )

    class _StubSector:
        def resolve_coin_sector(self, *_args, **_kwargs):
            return "Other"

    monkeypatch.setattr(processor, "resolve_sector_map", lambda *_a, **_k: _StubSector())
    monkeypatch.setattr(
        validation,
        "validate_and_blend_history",
        lambda **kwargs: validation.ValidationResult(
            passed=True,
            summary={
                "coin_id": kwargs["coin_id"],
                "symbol": kwargs["symbol"],
                "name": kwargs["name"],
                "validation_passed": True,
                "validation_reason": "ok",
                "latest_price_gap": float("nan"),
                "median_price_gap": float("nan"),
                "direct_market_cap_days": 0,
                "direct_price_days": 0,
                "history_days": 3,
                "overlap_days": 0,
                "latest_overlap_date": pd.NaT,
                "price_correlation": float("nan"),
                "market_cap_anchor": 1_000_000.0,
                "market_cap_anchor_price": 10.0,
            },
            blended_history=kwargs["cc_history"].rename(
                columns={"cc_price": "price", "cc_volume_usd": "volume_usd"}
            ).assign(market_cap=100_000.0),
        ),
    )

    panel, metadata = processor.build_processed_datasets(config, object())

    assert "newcoin" in set(panel["coin_id"])
    assert "newcoin" in set(metadata.index)
