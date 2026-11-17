from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


def _write_output_fixture(output_dir: Path) -> None:
    candles = output_dir / "candles"
    funding = output_dir / "funding"
    candles.mkdir(parents=True)
    funding.mkdir(parents=True)

    times = pd.date_range("2022-01-01T00:00:00Z", periods=5, freq="h")
    pd.DataFrame(
        {
            "open_time": times,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 10.0,
            "quote_volume": 10.0,
        }
    ).to_csv(candles / "BTCUSDT_market.csv", index=False)
    pd.DataFrame(
        {
            "coin_id": ["bitcoin", "wrapped-bitcoin"],
            "panel_symbol": ["BTC", "WBTC"],
            "bitget_symbol": ["BTCUSDT", "BTCUSDT"],
            "base_coin": ["BTC", "WBTC"],
            "contract_status": ["normal", "normal"],
            "reason": ["direct", "alias"],
            "fund_interval": [8, 8],
            "min_trade_usdt": [5, 5],
            "size_multiplier": [0.001, 0.001],
        }
    ).to_csv(output_dir / "symbol_map.csv", index=False)
    (output_dir / "funding" / "bitcoin.csv").write_text(
        "symbol,funding_time,funding_rate\n", encoding="utf-8"
    )
    (output_dir / "state.json").write_text(
        json.dumps(
            {
                "BTCUSDT_market": {
                    "2022-01-01T00:00:00+00:00": {
                        "status": "complete",
                        "rows": 3,
                        "expected_rows": 3,
                    },
                    "2022-01-01T03:00:00+00:00": {
                        "status": "complete",
                        "rows": 2,
                        "expected_rows": 2,
                    },
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    stale_rows = [
        {
            "coin_id": coin_id,
            "bitget_symbol": "BTCUSDT",
            "candle_type": "market",
            "rows": 1,
            "first": "2022-01-01T00:00:00+00:00",
            "last": "2022-01-01T00:00:00+00:00",
            "complete_windows": 0,
            "missing_windows": 2,
            "partial_windows": 0,
            "window_coverage": 0.0,
            "max_gap_hours": 9.0,
        }
        for coin_id in ("bitcoin", "wrapped-bitcoin")
    ]
    (output_dir / "coverage.json").write_text(
        json.dumps(stale_rows, indent=2), encoding="utf-8"
    )
    pd.DataFrame(stale_rows).to_csv(output_dir / "coverage.csv", index=False)
    (output_dir / "merge_manifest.json").write_text(
        json.dumps({"coverage_rows": 2, "candle_files": 0}, indent=2),
        encoding="utf-8",
    )


def test_reconcile_merged_metadata_recomputes_stale_coverage(tmp_path: Path) -> None:
    from scripts.merge_bitget_derivatives_shards import (
        reconcile_merged_metadata,
    )

    output_dir = tmp_path / "merged"
    _write_output_fixture(output_dir)

    manifest = reconcile_merged_metadata(output_dir)

    coverage = json.loads((output_dir / "coverage.json").read_text(encoding="utf-8"))
    csv_coverage = pd.read_csv(output_dir / "coverage.csv")
    assert manifest["coverage_rows"] == 2
    assert manifest["candle_files"] == 1
    assert manifest["funding_files"] == 1
    assert manifest["state_series"] == 1
    assert {row["coin_id"] for row in coverage} == {
        "bitcoin",
        "wrapped-bitcoin",
    }
    for row in coverage:
        assert row["rows"] == 5
        assert row["complete_windows"] == 2
        assert row["missing_windows"] == 0
        assert row["partial_windows"] == 0
        assert row["window_coverage"] == 1.0
        assert row["max_gap_hours"] == 1.0
    assert len(csv_coverage) == 2


def test_reconcile_merged_metadata_fails_when_a_state_series_has_no_file(
    tmp_path: Path,
) -> None:
    from scripts.merge_bitget_derivatives_shards import (
        reconcile_merged_metadata,
    )

    output_dir = tmp_path / "merged"
    _write_output_fixture(output_dir)
    (output_dir / "candles" / "BTCUSDT_market.csv").unlink()

    with pytest.raises(ValueError, match="state series has no candle file"):
        reconcile_merged_metadata(output_dir)


def test_reconcile_treats_pre_listing_gap_as_outside_coverage(
    tmp_path: Path,
) -> None:
    from scripts.merge_bitget_derivatives_shards import (
        reconcile_merged_metadata,
    )

    output_dir = tmp_path / "merged"
    _write_output_fixture(output_dir)
    state_path = output_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "BTCUSDT_market": {
                    "2022-01-01T00:00:00+00:00": {
                        "status": "complete",
                        "rows": 3,
                        "expected_rows": 3,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    candle_path = output_dir / "candles" / "BTCUSDT_market.csv"
    frame = pd.read_csv(candle_path)
    # The state window begins before the first venue print.  The first real
    # observation is at 02:00, which is inside the declared three-hour window;
    # this is a genuine pre-listing gap, not a truncated tail.
    frame.loc[frame.index == 2].to_csv(candle_path, index=False)

    manifest = reconcile_merged_metadata(output_dir)

    coverage = json.loads((output_dir / "coverage.json").read_text(encoding="utf-8"))
    assert manifest["coverage_rows"] == 2
    assert all(row["complete_windows"] == 1 for row in coverage)
    assert all(row["partial_windows"] == 0 for row in coverage)


def test_reconcile_rejects_truncated_tail_even_when_last_observation_is_present(
    tmp_path: Path,
) -> None:
    from scripts.merge_bitget_derivatives_shards import (
        reconcile_merged_metadata,
    )

    output_dir = tmp_path / "merged"
    _write_output_fixture(output_dir)
    state_path = output_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "BTCUSDT_market": {
                    "2022-01-01T00:00:00+00:00": {
                        "status": "complete",
                        "rows": 5,
                        "expected_rows": 5,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    candle_path = output_dir / "candles" / "BTCUSDT_market.csv"
    frame = pd.read_csv(candle_path)
    frame.loc[frame.index < 3].to_csv(candle_path, index=False)

    reconcile_merged_metadata(output_dir)

    coverage = json.loads((output_dir / "coverage.json").read_text(encoding="utf-8"))
    assert coverage
    assert all(row["complete_windows"] == 0 for row in coverage)
    assert all(row["partial_windows"] == 1 for row in coverage)
    assert all(row["window_coverage"] == 0.0 for row in coverage)
