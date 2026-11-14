from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from atlas20.derivatives import data_audit
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
                "panel_symbol": "BTC",
                "bitget_symbol": "BTCUSDT",
                "base_coin": "BTC",
                "contract_status": "normal",
                "reason": "direct",
                "fund_interval": 8,
                "min_trade_usdt": 5,
                "size_multiplier": 0.001,
            },
            {
                "coin_id": "ethereum",
                "panel_symbol": "ETH",
                "bitget_symbol": "",
                "base_coin": "",
                "contract_status": "missing",
                "reason": "no Bitget USDT-M perpetual",
                "fund_interval": None,
                "min_trade_usdt": None,
                "size_multiplier": None,
            },
        ]
    ).to_csv(symbol_map, index=False)

    contracts = raw / "contracts.json"
    contracts.write_text(
        json.dumps(
            [
                {
                    "symbol": "BTCUSDT",
                    "baseCoin": "BTC",
                    "quoteCoin": "USDT",
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
                    "symbol": "BTC" if coin == "bitcoin" else "ETH",
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


def test_zero_latest_market_cap_is_invalid_not_treated_as_a_real_value(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    panel = pd.read_csv(paths["panel"])
    mask = (panel["date"] == "2026-11-13") & (panel["coin_id"] == "bitcoin")
    panel.loc[mask, "market_cap"] = 0.0
    panel.to_csv(paths["panel"], index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("panel.latest_market_cap" in item for item in report.hard_failures)
    assert any("panel.valid_market_cap" in item for item in report.warnings)


def test_required_last_mark_time_waits_for_the_completed_execution_hour() -> None:
    before_fill = data_audit.required_last_mark_time(
        datetime(2026, 11, 14, 1, 4, tzinfo=timezone.utc)
    )
    at_fill = data_audit.required_last_mark_time(
        datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc)
    )

    assert before_fill == pd.Timestamp("2026-11-13T23:00:00Z")
    assert at_fill == pd.Timestamp("2026-11-14T00:00:00Z")


def test_missing_required_mark_bar_fails_even_when_a_newer_bar_exists(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame = frame.loc[
        pd.to_datetime(frame["open_time"], utc=True)
        != pd.Timestamp("2026-11-14T00:00:00Z")
    ]
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("required mark bar" in item for item in report.hard_failures)


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


def test_all_funding_must_be_fresh_for_the_live_short_sleeve(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    stale = pd.to_datetime(frame["funding_time"], utc=True) <= pd.Timestamp(
        "2026-11-12T16:00:00Z"
    )
    frame.loc[stale].to_csv(path, index=False)

    report = _audit(paths, require_all_funding_fresh=True)

    assert report.passed is False
    assert any("live short sleeve" in item for item in report.hard_failures)


def test_non_monotonic_funding_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = frame.iloc[[1, 0, 2, 3]]
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("not monotonic" in item for item in report.hard_failures)


def test_latest_panel_market_cap_must_be_finite(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    frame = pd.read_csv(paths["panel"])
    latest = frame["date"] == "2026-11-13"
    frame.loc[latest, "market_cap"] = float("nan")
    frame.to_csv(paths["panel"], index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("latest market-cap" in item for item in report.hard_failures)


def test_contract_base_identity_must_match_the_symbol_map(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    contracts = paths["raw"] / "contracts.json"
    payload = json.loads(contracts.read_text(encoding="utf-8"))
    payload[0]["baseCoin"] = "XBT"
    contracts.write_text(json.dumps(payload), encoding="utf-8")

    report = _audit(paths)

    assert report.passed is False
    assert any("base coin" in item for item in report.hard_failures)


def test_panel_symbol_drift_invalidates_a_stale_symbol_map(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    panel = pd.read_csv(paths["panel"])
    latest = panel["date"] == "2026-11-13"
    panel.loc[latest & panel["coin_id"].eq("bitcoin"), "symbol"] = "BTX"
    panel.to_csv(paths["panel"], index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("panel symbol drift" in item for item in report.hard_failures)


def test_panel_missing_symbol_fails_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    panel = pd.read_csv(paths["panel"])
    latest = panel["date"] == "2026-11-13"
    panel.loc[latest & panel["coin_id"].eq("bitcoin"), "symbol"] = ""
    panel.to_csv(paths["panel"], index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("panel.valid_symbols" in item for item in report.hard_failures)


def test_non_normal_map_row_cannot_keep_a_tradeable_symbol(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    frame = pd.read_csv(paths["symbol_map"])
    frame.loc[frame["coin_id"].eq("bitcoin"), "contract_status"] = "offline"
    frame.to_csv(paths["symbol_map"], index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("non-normal row" in item for item in report.hard_failures)


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
