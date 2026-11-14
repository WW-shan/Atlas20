from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from atlas20.derivatives.data_audit import audit_derivatives_data

NOW = datetime(2026, 11, 14, 2, 0, tzinfo=timezone.utc)


def _fixture(tmp_path: Path) -> dict[str, Path]:
    raw = tmp_path / "raw"
    candles = raw / "candles"
    funding = raw / "funding"
    candles.mkdir(parents=True)
    funding.mkdir(parents=True)

    symbol_map = raw / "symbol_map.csv"
    pd.DataFrame(
        [
            {
                "coin_id": "bitcoin",
                "bitget_symbol": "BTCUSDT",
                "contract_status": "normal",
                "reason": "direct",
                "fund_interval": 8,
                "min_trade_usdt": 5,
                "size_multiplier": 0.001,
            }
        ]
    ).to_csv(symbol_map, index=False)

    contracts = raw / "contracts.json"
    contracts.write_text(
        json.dumps(
            [
                {
                    "symbol": "BTCUSDT",
                    "symbolStatus": "normal",
                    "symbolType": "perpetual",
                    "minLever": "1",
                    "maxLever": "125",
                    "minTradeNum": "0.001",
                    "minTradeUSDT": "5",
                    "sizeMultiplier": "0.001",
                    "pricePlace": "1",
                    "priceEndStep": "1",
                    "takerFeeRate": "0.0006",
                    "fundInterval": "8",
                }
            ]
        ),
        encoding="utf-8",
    )

    index = pd.date_range("2026-11-13T00:00:00Z", "2026-11-14T01:00:00Z", freq="1h")
    pd.DataFrame(
        {
            "open_time": index,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
        }
    ).to_csv(candles / "BTCUSDT_mark.csv", index=False)

    funding_times = pd.date_range("2026-11-12T00:00:00Z", "2026-11-13T16:00:00Z", freq="8h")
    pd.DataFrame(
        {
            "symbol": "BTCUSDT",
            "funding_time": funding_times,
            "funding_rate": 0.0001,
        }
    ).to_csv(funding / "bitcoin.csv", index=False)
    funding_manifest = raw / "funding_manifest.json"
    funding_manifest.write_text(
        json.dumps(
            {
                "bitcoin": {
                    "cached": True,
                    "first": str(funding_times[0]),
                    "last": str(funding_times[-1]),
                    "rows": len(funding_times),
                    "symbol": "BTCUSDT",
                }
            }
        ),
        encoding="utf-8",
    )

    coverage = raw / "coverage.json"
    coverage.write_text(
        json.dumps(
            [
                {
                    "coin_id": "bitcoin",
                    "bitget_symbol": "BTCUSDT",
                    "candle_type": "mark",
                    "first": str(index[0]),
                    "last": str(index[-1]),
                    "rows": len(index),
                    "max_gap_hours": 1.0,
                    "missing_windows": 0,
                }
            ]
        ),
        encoding="utf-8",
    )

    panel = tmp_path / "panel.csv"
    panel_rows = []
    for day in ("2026-11-12", "2026-11-13"):
        for coin in ("bitcoin", "ethereum"):
            panel_rows.append(
                {
                    "date": day,
                    "coin_id": coin,
                    "price": 100.0,
                    "volume_usd": 1_000_000.0,
                    "market_cap": 10_000_000_000.0,
                }
            )
    pd.DataFrame(panel_rows).to_csv(panel, index=False)

    return {
        "raw": raw,
        "panel": panel,
        "symbol_map": symbol_map,
        "manifest": raw / "manifest.json",
    }


def _audit(paths: dict[str, Path], **kwargs):
    return audit_derivatives_data(
        paths["raw"],
        paths["panel"],
        paths["symbol_map"],
        paths["manifest"],
        now=NOW,
        min_panel_assets=1,
        **kwargs,
    )


def test_valid_fixture_passes_and_has_a_stable_fingerprint(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    first = _audit(paths)
    second = _audit(paths)

    assert first.passed is True
    assert first.hard_failures == []
    assert first.provenance["fingerprint"] == second.provenance["fingerprint"]
    assert first.provenance["fingerprint"].startswith("sha256:")


def test_duplicate_mark_timestamp_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame = pd.concat([frame, frame.iloc[[-1]]], ignore_index=True)
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("duplicate mark timestamp" in item for item in report.hard_failures)


def test_future_mark_timestamp_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame.loc[len(frame)] = ["2026-11-14T03:00:00+00:00", 100, 101, 99, 100]
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("future mark timestamp" in item for item in report.hard_failures)


def test_invalid_ohlc_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "high"] = 90.0
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("invalid OHLC" in item for item in report.hard_failures)


def test_stale_funding_fails_when_short_is_required(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = frame.loc[pd.to_datetime(frame["funding_time"], utc=True) <= pd.Timestamp("2026-11-12T16:00:00Z")]
    frame.to_csv(path, index=False)

    report = _audit(paths, required_short_assets={"bitcoin"})

    assert report.passed is False
    assert any("funding is stale" in item for item in report.hard_failures)


def test_ambiguous_symbol_mapping_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    frame = pd.read_csv(paths["symbol_map"])
    duplicate = frame.iloc[[0]].copy()
    duplicate.loc[:, "coin_id"] = "wrapped-bitcoin"
    duplicate.loc[:, "reason"] = "direct"
    pd.concat([frame, duplicate], ignore_index=True).to_csv(paths["symbol_map"], index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("ambiguous Bitget symbol" in item for item in report.hard_failures)


def test_panel_missing_last_completed_day_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    frame = pd.read_csv(paths["panel"])
    frame = frame.loc[frame["date"] != "2026-11-13"]
    frame.to_csv(paths["panel"], index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("panel does not reach the last completed UTC day" in item for item in report.hard_failures)
