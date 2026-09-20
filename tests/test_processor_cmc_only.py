"""The processed panel is built from a single provider: CoinMarketCap.

Price, volume and market cap must all come out of the same snapshot so the
price/market-cap ratio is internally consistent. Any leftover file from the
retired price sources must be ignored rather than silently merged in.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from atlas20.config import load_config, load_sector_config
from atlas20.data import processor


def _write_candidates(raw_dir: Path, *assets: dict) -> None:
    path = raw_dir / "coingecko" / "candidate_assets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(assets)), encoding="utf-8")


def _candidate(coin_id: str, symbol: str, cmc_id: int) -> dict:
    return {
        "id": coin_id,
        "symbol": symbol,
        "name": coin_id.title(),
        "market_cap": 1_000_000.0,
        "market_cap_rank": 1,
        "current_price": 100.0,
        "total_volume": 10_000.0,
        "cmc_id": cmc_id,
    }


def _write_cmc(
    raw_dir: Path,
    cmc_id: int,
    days: list[str],
    *,
    price: float = 250.0,
    volume: float = 9_000_000.0,
    market_cap: float | None = 5_000_000.0,
) -> None:
    directory = raw_dir / "coinmarketcap" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    start = int(pd.Timestamp(days[0]).timestamp())
    end = int(pd.Timestamp(days[-1]).timestamp())
    payload = [
        {
            "timeOpen": f"{d}T00:00:00.000Z",
            "quote": {
                "close": price,
                "volume": volume,
                "marketCap": market_cap,
                "circulatingSupply": 20_000.0,
            },
        }
        for d in days
    ]
    (directory / f"{cmc_id}_{start}_{end}.json").write_text(json.dumps(payload), encoding="utf-8")


def _config(tmp_path: Path):
    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    config.start_date = "2024-01-01"
    config.end_date = "2024-01-10"
    config.data_quality.min_price_days = 2
    config.data_quality.min_market_cap_days = 2
    return config


def _days() -> list[str]:
    return ["2024-01-01", "2024-01-02", "2024-01-03"]


def test_panel_uses_coinmarketcap_price_volume_and_market_cap(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())

    panel, metadata = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["price"]) == {250.0}
    assert set(panel["volume_usd"]) == {9_000_000.0}
    assert set(panel["market_cap"]) == {5_000_000.0}
    assert panel["price_source"].eq("coinmarketcap").all()
    assert panel["volume_source"].eq("coinmarketcap").all()
    assert panel["market_cap_source"].eq("coinmarketcap").all()
    assert metadata.loc["bitcoin", "sector"]


def test_retired_source_cache_is_ignored(tmp_path):
    """A stale CryptoCompare cache must not leak back into the panel."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())
    legacy = raw_dir / "cryptocompare" / "histoday" / "BTC.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        json.dumps(
            {
                "Response": "Success",
                "Data": {
                    "Data": [
                        {"time": int(pd.Timestamp(d).timestamp()), "close": 1.0, "volumeto": 1.0}
                        for d in _days()
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["price"]) == {250.0}, "legacy prices must not be spliced in"


def test_asset_without_coinmarketcap_history_is_skipped(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1), _candidate("ghost", "GHOST", 2))
    _write_cmc(raw_dir, 1, _days())

    panel, metadata = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}
    assert "ghost" not in metadata.index


def test_zero_market_cap_asset_never_enters_the_panel(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1), _candidate("whitebit", "WBT", 2))
    _write_cmc(raw_dir, 1, _days())
    _write_cmc(raw_dir, 2, _days(), market_cap=0.0)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["whitebit", "validation_reason"] == "insufficient_market_cap_history"
    assert not bool(quality.loc["whitebit", "validation_passed"])


def test_data_quality_keeps_the_api_contract_columns(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())

    processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv")
    required = {
        "symbol",
        "validation_passed",
        "validation_reason",
        "latest_overlap_date",
        "latest_price_gap",
        "median_price_gap",
        "price_correlation",
        "included_in_panel",
    }
    assert required <= set(quality.columns)
    assert quality.loc[0, "symbol"] == "BTC"
    assert bool(quality.loc[0, "included_in_panel"]) is True
