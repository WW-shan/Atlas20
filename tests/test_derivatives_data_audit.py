from __future__ import annotations

import hashlib
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
            "volume": 10.0,
            "quote_volume": 1_000.0,
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

    publication = raw / "funding_publication.json"
    publication.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-11-14T01:05:00+00:00",
                "assets": {
                    "bitcoin": {
                        "symbol": "BTCUSDT",
                        "funding_sha256": hashlib.sha256(
                            (funding / "bitcoin.csv").read_bytes()
                        ).hexdigest(),
                        "funding_last": str(funding_times[-1]),
                        "funding_rate": 0.0001,
                        "history_last": str(funding_times[-1]),
                        "history_request_time": "2026-11-14T01:00:00+00:00",
                        "current_settlement_time": str(funding_times[-1]),
                        "current_funding_rate": 0.0001,
                        "current_request_time": "2026-11-14T01:05:00+00:00",
                        "api_interval_hours": 8.0,
                        "contract_interval_hours": 8.0,
                        "interval_matches_contract": True,
                        "history_rate_at_current_settlement": 0.0001,
                        "rate_relation": "match",
                        "latest_source": "history",
                        "verified_at": "2026-11-14T01:05:00+00:00",
                        "publication_lag_seconds": 32700.0,
                        "history_lag_seconds": 32400.0,
                    }
                },
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


def test_funding_csv_bytes_are_part_of_the_provenance_fingerprint(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    first = _audit(paths)

    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "funding_rate"] = 0.0002
    frame.to_csv(path, index=False)

    second = _audit(paths)

    assert first.passed is True
    assert second.passed is True
    assert "funding/bitcoin.csv" in second.provenance["files"]
    assert second.provenance["fingerprint"] != first.provenance["fingerprint"]


def test_funding_publication_observation_time_does_not_change_data_fingerprint(
    tmp_path: Path,
) -> None:
    """A read-only audit may refresh observation evidence, not data identity."""

    paths = _fixture(tmp_path)
    first = _audit(paths)
    publication_path = paths["raw"] / "funding_publication.json"
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    publication["assets"]["bitcoin"]["verified_at"] = "2026-11-14T02:00:30+00:00"
    publication["assets"]["bitcoin"]["publication_lag_seconds"] = 12630.0
    publication_path.write_text(json.dumps(publication), encoding="utf-8")

    second = _audit(paths)

    assert first.passed is True
    assert second.passed is True
    assert first.provenance["fingerprint"] == second.provenance["fingerprint"]


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


def test_historical_market_cap_gap_is_unrankable_but_not_a_warning(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    panel = pd.read_csv(paths["panel"])
    mask = (panel["date"] == "2026-11-12") & (panel["coin_id"] == "bitcoin")
    panel.loc[mask, "market_cap"] = float("nan")
    panel.to_csv(paths["panel"], index=False)

    report = _audit(paths)

    assert report.passed is True
    assert report.hard_failures == []
    assert not any("panel.valid_market_cap" in item for item in report.warnings)


def test_required_last_mark_time_tracks_the_completed_daily_close() -> None:
    before_fill = data_audit.required_last_mark_time(
        datetime(2026, 11, 14, 1, 4, tzinfo=timezone.utc)
    )
    after_fill = data_audit.required_last_mark_time(
        datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc)
    )

    # The daily signal does not consume the 00:00 hourly mark bar.  The 01:05
    # clock is execution-only; both moments require the same completed daily
    # close.  The 01:00 market bar is audited separately as the fill anchor.
    assert before_fill == pd.Timestamp("2026-11-13T23:00:00Z")
    assert after_fill == pd.Timestamp("2026-11-13T23:00:00Z")


def test_missing_completed_daily_mark_close_fails_even_when_a_newer_bar_exists(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame = frame.loc[
        pd.to_datetime(frame["open_time"], utc=True)
        != pd.Timestamp("2026-11-13T23:00:00Z")
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
    frame.loc[len(frame)] = [
        "2026-11-14T03:00:00+00:00",
        100,
        101,
        99,
        100,
        10,
        1_000,
    ]
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


def test_non_hourly_mark_timestamp_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "open_time"] = "2026-11-13T00:30:00+00:00"
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("non-hourly mark open_time" in item for item in report.hard_failures)


def test_non_finite_mark_ohlc_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "high"] = float("inf")
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("invalid row" in item for item in report.hard_failures)


def test_invalid_mark_volume_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "volume"] = -1.0
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("invalid mark volume" in item for item in report.hard_failures)


def test_zero_mark_volume_is_valid(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    frame = pd.read_csv(path)
    frame.loc[:, ["volume", "quote_volume"]] = 0.0
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is True, report.hard_failures


def test_stale_funding_fails_when_short_is_required(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = frame.loc[pd.to_datetime(frame["funding_time"], utc=True) <= pd.Timestamp("2026-11-12T16:00:00Z")]
    frame.to_csv(path, index=False)

    report = _audit(paths, required_short_assets={"bitcoin"})

    assert report.passed is False
    # The hard proof is the missing scheduled settlement, not the redundant
    # wall-clock age warning.
    assert any("settlement_coverage" in item for item in report.hard_failures)
    assert any("funding is stale" in item for item in report.warnings)


def test_all_funding_is_checked_for_complete_coverage_when_requested(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    stale = pd.to_datetime(frame["funding_time"], utc=True) <= pd.Timestamp(
        "2026-11-12T16:00:00Z"
    )
    frame.loc[stale].to_csv(path, index=False)

    report = _audit(paths, require_all_funding_fresh=True)

    assert report.passed is False
    assert any("settlement_coverage" in item for item in report.hard_failures)


def test_non_monotonic_funding_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = frame.iloc[[1, 0, 2, 3]]
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("not monotonic" in item for item in report.hard_failures)


def test_missing_recent_funding_settlement_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = frame.drop(index=1).reset_index(drop=True)
    frame.to_csv(path, index=False)

    report = _audit(paths, require_all_funding_fresh=True)

    assert report.passed is False
    assert any("funding gap" in item for item in report.hard_failures)


def test_required_funding_asset_must_cover_every_scheduled_settlement(
    tmp_path: Path,
) -> None:
    """A fresh last row cannot hide an omitted settlement earlier in the window."""

    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = frame.drop(index=1).reset_index(drop=True)
    # Add the settlement that should have been published by the audit time so
    # the remaining failure is specifically the interior omission.
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                {
                    "symbol": ["BTCUSDT"],
                    "funding_time": ["2026-11-14T00:00:00+00:00"],
                    "funding_rate": [0.0001],
                }
            ),
        ],
        ignore_index=True,
    ).sort_values("funding_time")
    frame.to_csv(path, index=False)

    report = _audit(
        paths,
        required_funding_assets={"bitcoin"},
    )

    assert report.passed is False
    assert any("settlement_coverage" in item for item in report.hard_failures)


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


def test_required_short_leverage_must_be_supported_by_the_venue(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    contract_path = paths["raw"] / "contracts.json"
    contracts = json.loads(contract_path.read_text(encoding="utf-8"))
    contracts[0]["maxLever"] = "3"
    contract_path.write_text(json.dumps(contracts), encoding="utf-8")

    report = _audit(
        paths,
        required_short_assets={"bitcoin"},
        required_leverage=4.0,
    )

    assert report.passed is False
    assert any("leverage" in item and "bitcoin" in item for item in report.hard_failures)


def test_required_leverage_is_checked_for_every_target_asset(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    contract_path = paths["raw"] / "contracts.json"
    contracts = json.loads(contract_path.read_text(encoding="utf-8"))
    contracts[0]["maxLever"] = "3"
    contract_path.write_text(json.dumps(contracts), encoding="utf-8")

    report = _audit(
        paths,
        required_leverage_assets={"bitcoin"},
        required_leverage=4.0,
    )

    assert report.passed is False
    assert any(
        item.startswith("contracts.bitcoin.required_leverage:")
        for item in report.hard_failures
    )


def test_target_asset_reader_covers_latest_longs_and_shorts_separately(tmp_path: Path) -> None:
    from scripts.audit_derivatives_data import _required_short_assets, _target_assets

    targets = tmp_path / "targets.csv"
    pd.DataFrame(
        [
            {"signal_date": "2026-11-12", "asset": "old", "target_weight": -0.25},
            {"signal_date": "2026-11-13", "asset": "bitcoin", "target_weight": 0.75},
            {"signal_date": "2026-11-13", "asset": "near", "target_weight": -0.50},
        ]
    ).to_csv(targets, index=False)

    assert _target_assets(targets) == {"bitcoin", "near"}
    assert _required_short_assets(targets) == {"near"}


def test_required_leverage_asset_without_a_live_mapping_fails_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    report = _audit(
        paths,
        required_leverage_assets={"ethereum"},
        required_leverage=4.0,
    )

    assert report.passed is False
    assert any(
        "required_leverage" in item and "ethereum" in item
        for item in report.hard_failures
    )


def test_required_funding_freshness_is_informational_when_calendar_is_complete(
    tmp_path: Path,
) -> None:
    """A complete settlement calendar is the hard gate; wall-clock age is a warning.

    At 01:05 UTC the newest normal 8h settlement (00:00) is legitimately only
    minutes old in a freshly downloaded tree, but at 08:59 UTC it can look
    older than the declared interval while still being the newest settlement
    the provider should have published.  The audit must not call that a second
    hard failure after proving every scheduled row exists.
    """

    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                {
                    "symbol": ["BTCUSDT"],
                    "funding_time": ["2026-11-14T00:00:00+00:00"],
                    "funding_rate": [0.0001],
                }
            ),
        ],
        ignore_index=True,
    ).sort_values("funding_time")
    frame.to_csv(path, index=False)
    manifest_path = paths["raw"] / "funding_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bitcoin"]["last"] = "2026-11-14 00:00:00+00:00"
    manifest["bitcoin"]["rows"] = len(frame)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    publication_path = paths["raw"] / "funding_publication.json"
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    entry = publication["assets"]["bitcoin"]
    entry["funding_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    entry["funding_last"] = "2026-11-14 00:00:00+00:00"
    entry["history_last"] = "2026-11-14 00:00:00+00:00"
    entry["current_settlement_time"] = "2026-11-14 00:00:00+00:00"
    entry["publication_lag_seconds"] = 3900.0
    entry["history_lag_seconds"] = 3600.0
    publication_path.write_text(json.dumps(publication), encoding="utf-8")

    report = audit_derivatives_data(
        paths["raw"],
        paths["panel"],
        paths["symbol_map"],
        paths["manifest"],
        now=datetime(2026, 11, 14, 8, 59, tzinfo=timezone.utc),
        min_panel_assets=1,
        required_funding_assets={"bitcoin"},
        funding_stale_hours=1.0,
    )

    assert report.passed is True
    stale_checks = [
        item for item in report.warnings if item.startswith("funding.bitcoin.fresh:")
    ]
    assert stale_checks, report.warnings
    assert not any("settlement_coverage" in item for item in report.hard_failures)


def test_funding_file_symbol_must_match_the_mapped_contract(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame["symbol"] = "ETHUSDT"
    frame.to_csv(path, index=False)

    report = _audit(paths, required_funding_assets={"bitcoin"})

    assert report.passed is False
    assert any("funding.bitcoin.symbol" in item for item in report.hard_failures)


def test_symbol_map_funding_interval_must_match_the_contract(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    symbol_map = pd.read_csv(paths["symbol_map"])
    symbol_map.loc[symbol_map["coin_id"] == "bitcoin", "fund_interval"] = 4
    symbol_map.to_csv(paths["symbol_map"], index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("fund_interval_matches" in item for item in report.hard_failures)


def test_absurd_funding_rate_is_rejected(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "funding_rate"] = 0.50
    frame.to_csv(path, index=False)

    report = _audit(paths, required_funding_assets={"bitcoin"})

    assert report.passed is False
    assert any("rate_sanity" in item for item in report.hard_failures)


def test_funding_timestamp_grid_must_match_the_declared_interval(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                {
                    "symbol": ["BTCUSDT"],
                    "funding_time": ["2026-11-13T04:00:00+00:00"],
                    "funding_rate": [0.0001],
                }
            ),
        ],
        ignore_index=True,
    ).sort_values("funding_time")
    frame.to_csv(path, index=False)

    report = _audit(paths, require_all_funding_fresh=True)

    assert report.passed is False
    assert any("observed_gap_grid" in item for item in report.hard_failures)


def test_funding_interval_history_rejects_eight_hour_rows_for_declared_four(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    symbol_map = pd.read_csv(paths["symbol_map"])
    symbol_map.loc[symbol_map["coin_id"] == "bitcoin", "fund_interval"] = 4
    symbol_map.to_csv(paths["symbol_map"], index=False)
    contracts_path = paths["raw"] / "contracts.json"
    contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
    contracts[0]["fundInterval"] = "4"
    contracts_path.write_text(json.dumps(contracts), encoding="utf-8")

    report = _audit(paths)

    assert report.passed is False
    assert any("funding.bitcoin.interval_history" in item for item in report.hard_failures)


def test_funding_interval_history_rejects_four_hour_rows_for_declared_eight(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    frame = pd.read_csv(path)
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                {
                    "symbol": ["BTCUSDT"],
                    "funding_time": ["2026-11-13T04:00:00+00:00"],
                    "funding_rate": [0.0001],
                }
            ),
        ],
        ignore_index=True,
    ).sort_values("funding_time")
    frame.to_csv(path, index=False)

    report = _audit(paths)

    assert report.passed is False
    assert any("funding.bitcoin.interval_history" in item for item in report.hard_failures)


def test_funding_interval_history_checks_older_than_the_recent_gap_window(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    symbol_map = pd.read_csv(paths["symbol_map"])
    symbol_map.loc[symbol_map["coin_id"] == "bitcoin", "fund_interval"] = 4
    symbol_map.to_csv(paths["symbol_map"], index=False)
    contracts_path = paths["raw"] / "contracts.json"
    contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
    contracts[0]["fundInterval"] = "4"
    contracts_path.write_text(json.dumps(contracts), encoding="utf-8")

    old_eight_hour = pd.date_range(
        "2026-09-01T00:00:00Z", "2026-09-30T20:00:00Z", freq="8h"
    )
    recent_four_hour = pd.date_range(
        "2026-10-01T00:00:00Z", "2026-11-13T16:00:00Z", freq="4h"
    )
    times = old_eight_hour.append(recent_four_hour)
    pd.DataFrame(
        {
            "symbol": "BTCUSDT",
            "funding_time": times,
            "funding_rate": 0.0001,
        }
    ).to_csv(paths["raw"] / "funding" / "bitcoin.csv", index=False)
    manifest_path = paths["raw"] / "funding_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bitcoin"]["first"] = str(times[0])
    manifest["bitcoin"]["last"] = str(times[-1])
    manifest["bitcoin"]["rows"] = len(times)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = _audit(paths)

    assert report.passed is False
    assert any("funding.bitcoin.interval_history" in item for item in report.hard_failures)


def test_funding_audit_summary_records_the_observed_cadence(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    report = _audit(paths)

    assert report.passed is True
    assert report.summary["funding"]["bitcoin"]["observed_interval_hours"] == 8.0
    assert report.summary["funding"]["bitcoin"]["interval_matches_contract"] is True



def test_required_funding_needs_matching_publication_evidence(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    (paths["raw"] / "funding_publication.json").unlink()

    report = _audit(paths, required_funding_assets={"bitcoin"})

    assert report.passed is False
    assert any(
        "funding.bitcoin.publication_evidence" in item
        for item in report.hard_failures
    )


def test_publication_evidence_cannot_predate_latest_settlement(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    publication_path = paths["raw"] / "funding_publication.json"
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    publication["assets"]["bitcoin"]["verified_at"] = "2026-11-13T15:00:00+00:00"
    publication["assets"]["bitcoin"]["publication_lag_seconds"] = -3600.0
    publication_path.write_text(json.dumps(publication), encoding="utf-8")

    report = _audit(paths, required_funding_assets={"bitcoin"})

    assert report.passed is False
    assert any(
        "funding.bitcoin.publication_time" in item
        for item in report.hard_failures
    )


def test_publication_evidence_rejects_a_current_rate_conflict(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    publication_path = paths["raw"] / "funding_publication.json"
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    entry = publication["assets"]["bitcoin"]
    entry["rate_relation"] = "conflict"
    entry["current_funding_rate"] = 0.0009
    publication_path.write_text(json.dumps(publication), encoding="utf-8")

    report = _audit(paths, required_funding_assets={"bitcoin"})

    assert report.passed is False
    assert any(
        "funding.bitcoin.publication_rate" in item
        for item in report.hard_failures
    )


def test_publication_evidence_must_match_the_funding_file_hash(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    publication_path = paths["raw"] / "funding_publication.json"
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    publication["assets"]["bitcoin"]["funding_sha256"] = "0" * 64
    publication_path.write_text(json.dumps(publication), encoding="utf-8")

    report = _audit(paths, required_funding_assets={"bitcoin"})

    assert report.passed is False
    assert any(
        "funding.bitcoin.publication_hash" in item
        for item in report.hard_failures
    )


def test_required_empty_funding_file_fails_closed_without_crashing(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    path = paths["raw"] / "funding" / "bitcoin.csv"
    pd.DataFrame(columns=["symbol", "funding_time", "funding_rate"]).to_csv(
        path, index=False
    )
    publication_path = paths["raw"] / "funding_publication.json"
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    publication["assets"]["bitcoin"]["funding_sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    publication_path.write_text(json.dumps(publication), encoding="utf-8")

    report = _audit(paths, required_funding_assets={"bitcoin"})

    assert report.passed is False
    assert any(
        "funding.bitcoin.publication_evidence" in item
        for item in report.hard_failures
    )


def test_publication_evidence_uses_observation_clock_not_market_evaluation_clock(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    mark_path = paths["raw"] / "candles" / "BTCUSDT_mark.csv"
    marks = pd.read_csv(mark_path)
    mark_times = pd.to_datetime(marks["open_time"], utc=True)
    marks.loc[
        mark_times <= pd.Timestamp("2026-11-14T00:00:00Z")
    ].to_csv(mark_path, index=False)
    publication_path = paths["raw"] / "funding_publication.json"
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    entry = publication["assets"]["bitcoin"]
    entry["verified_at"] = "2026-11-14T01:00:00+00:00"
    entry["publication_lag_seconds"] = 32400.0
    publication_path.write_text(json.dumps(publication), encoding="utf-8")

    report = audit_derivatives_data(
        paths["raw"],
        paths["panel"],
        paths["symbol_map"],
        paths["manifest"],
        now=datetime(2026, 11, 14, 0, 30, tzinfo=timezone.utc),
        publication_now=datetime(2026, 11, 14, 2, 0, tzinfo=timezone.utc),
        min_panel_assets=1,
        required_funding_assets={"bitcoin"},
    )

    assert report.passed is True, report.hard_failures
    assert not any(
        "publication_time" in item for item in report.hard_failures
    )


def test_provenance_fingerprint_is_independent_of_audit_clock_and_manifest_bytes(
    tmp_path: Path,
) -> None:
    """A read-only re-audit must not change the data identity it reports."""

    from datetime import date, datetime, timezone
    from atlas20.derivatives.data_audit import audit_derivatives_data

    paths = _fixture(tmp_path)
    manifest_path = paths["manifest"]
    manifest_path.write_text(json.dumps({"data_fingerprint": "sha256:example"}), encoding="utf-8")
    first = audit_derivatives_data(
        paths["raw"],
        paths["panel"],
        paths["symbol_map"],
        manifest_path,
        now=datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc),
        expected_panel_day=date(2026, 11, 13),
        required_leverage=4.0,
    )
    first_fingerprint = first.provenance["fingerprint"]
    first_manifest_sha = first.provenance.get("manifest_sha256")

    # Reformatting the manifest changes its bytes but not the data inputs.
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(
        json.dumps(payload, indent=4, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    second = audit_derivatives_data(
        paths["raw"],
        paths["panel"],
        paths["symbol_map"],
        manifest_path,
        now=datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc),
        expected_panel_day=date(2026, 11, 13),
        required_leverage=4.0,
    )

    assert second.provenance["fingerprint"] == first_fingerprint
    audit_manifest_after = second.provenance.get("manifest_sha256")
    assert first_manifest_sha is not None
    assert audit_manifest_after is not None
    assert audit_manifest_after != first_manifest_sha


def test_provenance_fingerprint_is_independent_of_the_audit_time(tmp_path: Path) -> None:
    """Wall-clock fields in the audit payload are not data provenance."""

    from datetime import date, datetime, timezone
    from atlas20.derivatives.data_audit import audit_derivatives_data

    paths = _fixture(tmp_path)
    paths["manifest"].write_text(json.dumps({"data_fingerprint": "sha256:example"}), encoding="utf-8")
    first = audit_derivatives_data(
        paths["raw"],
        paths["panel"],
        paths["symbol_map"],
        paths["manifest"],
        now=datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc),
        expected_panel_day=date(2026, 11, 13),
        required_leverage=4.0,
    )
    second = audit_derivatives_data(
        paths["raw"],
        paths["panel"],
        paths["symbol_map"],
        paths["manifest"],
        now=datetime(2026, 11, 14, 3, 5, tzinfo=timezone.utc),
        expected_panel_day=date(2026, 11, 13),
        required_leverage=4.0,
    )

    assert second.provenance["fingerprint"] == first.provenance["fingerprint"]


def test_provenance_fingerprint_is_independent_of_raw_dir_path_spelling(
    tmp_path: Path,
) -> None:
    """The same snapshot must have one identity across finalize and execute."""

    from datetime import date, datetime, timezone
    from atlas20.derivatives.data_audit import audit_derivatives_data

    paths = _fixture(tmp_path)
    paths["manifest"].write_text(
        json.dumps({"data_fingerprint": "sha256:example"}),
        encoding="utf-8",
    )
    import os

    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        relative_raw = paths["raw"].relative_to(tmp_path)
        relative_panel = paths["panel"].relative_to(tmp_path)
        relative_symbol_map = paths["symbol_map"].relative_to(tmp_path)
        relative_manifest = paths["manifest"].relative_to(tmp_path)
        first = audit_derivatives_data(
            relative_raw,
            relative_panel,
            relative_symbol_map,
            relative_manifest,
            now=datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc),
            expected_panel_day=date(2026, 11, 13),
            required_leverage=4.0,
        )
        second = audit_derivatives_data(
            paths["raw"].resolve(),
            paths["panel"],
            paths["symbol_map"],
            paths["manifest"],
            now=datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc),
            expected_panel_day=date(2026, 11, 13),
            required_leverage=4.0,
        )
    finally:
        os.chdir(previous_cwd)

    assert first.provenance["files"] == second.provenance["files"]
    assert first.provenance["fingerprint"] == second.provenance["fingerprint"]
