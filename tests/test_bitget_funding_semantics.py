from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.audit_bitget_funding_semantics import (
    _build_fills,
    _expected_cycle_funding,
    _reconstruct_size_at,
    audit_funding_semantics,
)


def test_short_fills_increase_on_sell_and_reduce_on_buy() -> None:
    orders = [
        {"posSide": "short", "side": "sell", "cumExecQty": "0.4", "updatedTime": "1000"},
        {"posSide": "short", "side": "buy", "cumExecQty": "0.1", "updatedTime": "2000"},
    ]

    fills = _build_fills(orders, side=-1.0, pos_side="short")

    assert fills == [(1000, 0.4), (2000, -0.1)]
    assert _reconstruct_size_at(fills=fills, settlement_ms=1500) == pytest.approx(0.4)
    assert _reconstruct_size_at(fills=fills, settlement_ms=2500) == pytest.approx(0.3)


def test_short_funding_uses_positive_rate_as_a_credit() -> None:
    expected, rows = _expected_cycle_funding(
        side=-1.0,
        fills=[(1000, 2.0)],
        settlement_rows=[
            {
                "funding_time": pd.Timestamp("2026-01-01T00:00:00Z"),
                "funding_rate": 0.001,
                "mark_price": 100.0,
            }
        ],
    )

    # A short receives 0.001 * 2 * 100 when the rate is positive.
    assert expected == pytest.approx(0.2)
    assert rows[0]["amount"] == pytest.approx(0.2)


def test_long_funding_uses_positive_rate_as_a_debit() -> None:
    expected, _ = _expected_cycle_funding(
        side=1.0,
        fills=[(1000, 2.0)],
        settlement_rows=[
            {
                "funding_time": pd.Timestamp("2026-01-01T00:00:00Z"),
                "funding_rate": 0.001,
                "mark_price": 100.0,
            }
        ],
    )

    assert expected == pytest.approx(-0.2)


def _write_cycle_fixture(tmp_path: Path, *, reported: float) -> tuple[Path, Path]:
    raw = tmp_path / "raw"
    (raw / "funding").mkdir(parents=True)
    (raw / "candles").mkdir()
    pd.DataFrame(
        {
            "symbol": ["AAAUSDT", "AAAUSDT"],
            "funding_time": ["2026-01-01T08:00:00+00:00", "2026-01-01T16:00:00+00:00"],
            "funding_rate": [0.001, -0.0005],
        }
    ).to_csv(raw / "funding" / "aaa.csv", index=False)
    pd.DataFrame(
        {
            "open_time": ["2026-01-01T08:00:00+00:00", "2026-01-01T16:00:00+00:00"],
            "close": [100.0, 110.0],
        }
    ).to_csv(raw / "candles" / "AAAUSDT_mark.csv", index=False)
    pd.DataFrame(
        {"coin_id": ["aaa"], "bitget_symbol": ["AAAUSDT"]}
    ).to_csv(raw / "symbol_map.csv", index=False)
    return raw, raw / "symbol_map.csv"


def test_semantics_audit_reconstructs_a_short_cycle(tmp_path: Path) -> None:
    raw, symbol_map = _write_cycle_fixture(tmp_path, reported=0.09)

    opened = int(pd.Timestamp("2026-01-01T01:00:00Z").timestamp() * 1000)
    closed = int(pd.Timestamp("2026-01-01T17:00:00Z").timestamp() * 1000)

    def order_loader(**_: object) -> list[dict[str, object]]:
        return [
            {"posSide": "short", "side": "sell", "cumExecQty": "2", "updatedTime": str(opened + 1)},
        ]

    result = audit_funding_semantics(
        raw_dir=raw,
        symbol_map=symbol_map,
        position_history=[
            {
                "positionId": "p1",
                "symbol": "AAAUSDT",
                "posSide": "short",
                "createdTime": str(opened),
                "updatedTime": str(closed),
                "totalFunding": "0.09",
            }
        ],
        order_loader=order_loader,
        max_absolute_error=1e-9,
    )

    assert result["passed"] is True
    cycle = result["cycles"][0]
    # settlement 1: +0.001 * 2 * 100 = +0.2
    # settlement 2: -0.0005 * 2 * 110 = -0.11 -> total +0.09
    assert cycle["reconstructed_funding"] == pytest.approx(0.09)
    assert cycle["settlements"] == 2


def test_semantics_audit_fails_a_mismatched_total_funding(tmp_path: Path) -> None:
    raw, symbol_map = _write_cycle_fixture(tmp_path, reported=0.5)

    opened = int(pd.Timestamp("2026-01-01T01:00:00Z").timestamp() * 1000)
    closed = int(pd.Timestamp("2026-01-01T17:00:00Z").timestamp() * 1000)

    def order_loader(**_: object) -> list[dict[str, object]]:
        return [
            {"posSide": "short", "side": "sell", "cumExecQty": "2", "updatedTime": str(opened + 1)},
        ]

    result = audit_funding_semantics(
        raw_dir=raw,
        symbol_map=symbol_map,
        position_history=[
            {
                "positionId": "p1",
                "symbol": "AAAUSDT",
                "posSide": "short",
                "createdTime": str(opened),
                "updatedTime": str(closed),
                "totalFunding": "0.5",
            }
        ],
        order_loader=order_loader,
        max_absolute_error=1e-9,
    )

    assert result["passed"] is False
    assert result["hard_failures"]


def test_semantics_report_is_json_serializable(tmp_path: Path) -> None:
    raw, symbol_map = _write_cycle_fixture(tmp_path, reported=0.09)

    opened = int(pd.Timestamp("2026-01-01T01:00:00Z").timestamp() * 1000)
    closed = int(pd.Timestamp("2026-01-01T17:00:00Z").timestamp() * 1000)

    def order_loader(**_: object) -> list[dict[str, object]]:
        return [
            {"posSide": "short", "side": "sell", "cumExecQty": "2", "updatedTime": str(opened + 1)},
        ]

    result = audit_funding_semantics(
        raw_dir=raw,
        symbol_map=symbol_map,
        position_history=[
            {
                "positionId": "p1",
                "symbol": "AAAUSDT",
                "posSide": "short",
                "createdTime": str(opened),
                "updatedTime": str(closed),
                "totalFunding": "0.09",
            }
        ],
        order_loader=order_loader,
        max_absolute_error=1e-9,
    )
    json.dumps(result, default=str)
