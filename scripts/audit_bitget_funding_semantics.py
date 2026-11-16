"""Validate Bitget ``totalFunding`` against reconstructed position cycles.

The check is deliberately based on venue history, not on our journal:

- ``position_history`` supplies the exact closed ``positionId`` cycle and its
  reported cumulative ``totalFunding``.
- ``order_history_all`` supplies the fills that changed that position's size.
- The local funding tree supplies the settlement timestamps and rates.
- The local mark tree supplies the mark close at each settlement.

For a position with signed side ``s = +1`` (long) or ``-1`` (short), Bitget's
reported cumulative funding matches::

    totalFunding = sum(-s * funding_rate * position_qty * mark_price)

over settlements strictly inside the position cycle.  This makes the sign
convention explicit: positive funding is a credit to the position and negative
funding is a debit, independent of whether the position is long or short.

The residual is expected to be small because the local mark tree is a 1-hour
snapshot while the venue applies its exact settlement mark.  The audit refuses
to call a cycle valid when the residual exceeds a tight absolute/relative bound.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_oos_20261112")
DEFAULT_OUTPUT = Path("reports/ls45_live_g175/funding_semantics_audit.json")


@dataclass
class CycleResult:
    position_id: str
    symbol: str
    side: str
    opened_at: str
    closed_at: str
    settlements: int
    reconstructed_funding: float
    reported_funding: float
    absolute_error: float
    relative_error: float
    passed: bool
    detail: str
    settlement_rows: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "settlements": self.settlements,
            "reconstructed_funding": self.reconstructed_funding,
            "reported_funding": self.reported_funding,
            "absolute_error": self.absolute_error,
            "relative_error": self.relative_error,
            "passed": self.passed,
            "detail": self.detail,
            "settlement_rows": self.settlement_rows,
        }


def _side_sign(pos_side: object) -> float:
    value = str(pos_side or "").strip().lower()
    if value == "long":
        return 1.0
    if value == "short":
        return -1.0
    raise ValueError(f"unsupported position side: {pos_side!r}")


def _client_oid_side(side: object) -> float:
    value = str(side or "").strip().lower()
    if value == "buy":
        return 1.0
    if value == "sell":
        return -1.0
    raise ValueError(f"unsupported order side: {side!r}")


def _load_mark_series(raw_dir: Path, symbol: str) -> pd.Series:
    path = raw_dir / "candles" / f"{symbol.upper()}_mark.csv"
    if not path.is_file():
        raise FileNotFoundError(f"missing mark file: {path}")
    frame = pd.read_csv(path, usecols=["open_time", "close"])
    times = pd.to_datetime(frame["open_time"], utc=True, format="mixed", errors="coerce")
    closes = pd.to_numeric(frame["close"], errors="coerce")
    valid = times.notna() & closes.notna() & closes.gt(0.0)
    series = pd.Series(
        closes.loc[valid].to_numpy(dtype=float),
        index=pd.DatetimeIndex(times.loc[valid]),
        dtype=float,
    )
    series = series[~series.index.duplicated(keep="last")].sort_index()
    if series.empty:
        raise ValueError(f"mark file has no valid closes: {path}")
    return series


def _load_funding_frame(raw_dir: Path, coin_id: str) -> pd.DataFrame:
    path = raw_dir / "funding" / f"{coin_id}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"missing funding file: {path}")
    frame = pd.read_csv(path)
    if "funding_time" not in frame.columns or "funding_rate" not in frame.columns:
        raise ValueError(f"funding file missing funding_time/funding_rate: {path}")
    frame["funding_time"] = pd.to_datetime(
        frame["funding_time"], utc=True, format="mixed", errors="coerce"
    )
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    return frame.loc[
        frame["funding_time"].notna() & frame["funding_rate"].notna()
    ].sort_values("funding_time")


def _reconstruct_size_at(
    *,
    fills: list[tuple[int, float]],
    settlement_ms: int,
) -> float:
    """Return the positive position size held at a settlement timestamp.

    ``fills`` contains ``(updated_ms, signed_delta)`` where a positive delta
    increases the position in its own direction.  For a short, a sell is +qty
    and a buy is -qty; for a long the reverse.
    """

    size = 0.0
    for updated_ms, signed_delta in fills:
        if updated_ms > settlement_ms:
            break
        size += signed_delta
    return max(0.0, size)


def _build_fills(
    orders: list[dict[str, Any]],
    *,
    side: float,
    pos_side: str,
) -> list[tuple[int, float]]:
    fills: list[tuple[int, float]] = []
    for order in orders:
        if not isinstance(order, dict):
            continue
        row_pos_side = str(order.get("posSide") or "").strip().lower()
        if row_pos_side and row_pos_side != pos_side:
            continue
        try:
            quantity = float(order.get("cumExecQty") or 0.0)
            updated_ms = int(order.get("updatedTime") or order.get("createdTime") or 0)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(quantity) or quantity <= 0.0 or updated_ms <= 0:
            continue
        signed_delta = side * _client_oid_side(order.get("side")) * quantity
        fills.append((updated_ms, signed_delta))
    fills.sort(key=lambda item: item[0])
    return fills


def _expected_cycle_funding(
    *,
    side: float,
    fills: list[tuple[int, float]],
    settlement_rows: list[dict[str, Any]],
) -> tuple[float, list[dict[str, Any]]]:
    expected = 0.0
    detail_rows: list[dict[str, Any]] = []
    for row in settlement_rows:
        settlement = pd.Timestamp(row["funding_time"])
        settlement_ms = int(settlement.timestamp() * 1000)
        size = _reconstruct_size_at(fills=fills, settlement_ms=settlement_ms)
        if size <= 0.0:
            detail_rows.append({**row, "position_qty": size, "amount": 0.0})
            continue
        amount = -side * float(row["funding_rate"]) * size * float(row["mark_price"])
        expected += amount
        detail_rows.append({**row, "position_qty": size, "amount": amount})
    return float(expected), detail_rows


def _cycle_rows(
    *,
    raw_dir: Path,
    symbol_to_coin: dict[str, str],
    position_rows: list[dict[str, Any]],
    order_loader: Any,
    max_absolute_error: float,
    max_relative_error: float,
) -> list[CycleResult]:
    results: list[CycleResult] = []
    for row in position_rows:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        coin_id = symbol_to_coin.get(symbol)
        if not coin_id:
            continue
        side = _side_sign(row.get("posSide"))
        pos_side = str(row.get("posSide") or "").strip().lower()
        try:
            opened_ms = int(row.get("createdTime"))
            closed_ms = int(row.get("updatedTime"))
            reported = float(row.get("totalFunding") or 0.0)
        except (TypeError, ValueError):
            continue
        # Include the opening order and any fill just before the cycle boundary.
        orders = order_loader(
            symbol=symbol,
            start_time_ms=opened_ms - 2 * 60 * 60 * 1000,
            end_time_ms=closed_ms + 60 * 1000,
        )
        fills = _build_fills(orders, side=side, pos_side=pos_side)
        funding = _load_funding_frame(raw_dir, coin_id)
        marks = _load_mark_series(raw_dir, symbol)
        opened = pd.Timestamp(opened_ms, unit="ms", tz="UTC")
        closed = pd.Timestamp(closed_ms, unit="ms", tz="UTC")
        rows: list[dict[str, Any]] = []
        for settlement in funding.loc[
            (funding["funding_time"] > opened)
            & (funding["funding_time"] <= closed)
        ].itertuples(index=False):
            stamp = pd.Timestamp(settlement.funding_time)
            if stamp not in marks.index:
                raise ValueError(f"missing mark for {symbol} at {stamp}")
            rows.append(
                {
                    "funding_time": stamp,
                    "funding_rate": float(settlement.funding_rate),
                    "mark_price": float(marks.loc[stamp]),
                }
            )
        reconstructed, detail_rows = _expected_cycle_funding(
            side=side,
            fills=fills,
            settlement_rows=rows,
        )
        absolute_error = abs(reconstructed - reported)
        relative_error = absolute_error / max(abs(reported), 1e-12)
        tolerance = max(float(max_absolute_error), abs(reported) * float(max_relative_error))
        passed = bool(rows) and absolute_error <= tolerance
        results.append(
            CycleResult(
                position_id=str(row.get("positionId") or ""),
                symbol=symbol,
                side=pos_side,
                opened_at=opened.isoformat(),
                closed_at=closed.isoformat(),
                settlements=len(rows),
                reconstructed_funding=reconstructed,
                reported_funding=reported,
                absolute_error=absolute_error,
                relative_error=relative_error,
                passed=passed,
                detail=(
                    f"{len(rows)} settlement(s); tolerance={tolerance:.10g}; "
                    f"fills={len(fills)}"
                ),
                settlement_rows=[
                    {
                        **{
                            key: value.isoformat() if isinstance(value, pd.Timestamp) else value
                            for key, value in detail_row.items()
                        }
                    }
                    for detail_row in detail_rows
                ],
            )
        )
    return results


def audit_funding_semantics(
    *,
    raw_dir: Path,
    symbol_map: Path,
    position_history: list[dict[str, Any]],
    order_loader: Any,
    max_absolute_error: float = 1e-4,
    max_relative_error: float = 0.03,
) -> dict[str, Any]:
    symbol_frame = pd.read_csv(symbol_map)
    symbol_to_coin = {
        str(row.bitget_symbol).upper(): str(row.coin_id)
        for row in symbol_frame.itertuples(index=False)
        if pd.notna(row.bitget_symbol) and str(row.bitget_symbol).strip()
    }
    cycles = _cycle_rows(
        raw_dir=Path(raw_dir),
        symbol_to_coin=symbol_to_coin,
        position_rows=position_history,
        order_loader=order_loader,
        max_absolute_error=float(max_absolute_error),
        max_relative_error=float(max_relative_error),
    )
    failures = [cycle.as_dict() for cycle in cycles if not cycle.passed]
    max_abs = max((cycle.absolute_error for cycle in cycles), default=float("nan"))
    max_rel = max((cycle.relative_error for cycle in cycles), default=float("nan"))
    return {
        "semantics": (
            "totalFunding = signed cumulative funding per positionId cycle; "
            "positive is a credit to the position; settlement amount uses "
            "-side * rate * position_qty * mark_price"
        ),
        "cycles": [cycle.as_dict() for cycle in cycles],
        "cycle_count": len(cycles),
        "max_absolute_error": max_abs,
        "max_relative_error": max_rel,
        "hard_failures": failures,
        "passed": bool(cycles) and not failures,
    }


def main(argv: list[str] | None = None) -> int:
    from atlas20.derivatives.account import BitgetCredentials, BitgetPrivateClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--symbol-map", type=Path, default=None)
    parser.add_argument("--start", type=str, default="2026-11-14")
    parser.add_argument("--end", type=str, default="2026-11-16")
    parser.add_argument("--max-absolute-error", type=float, default=1e-4)
    parser.add_argument("--max-relative-error", type=float, default=0.03)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    if end <= start:
        raise SystemExit("--end must be after --start")
    symbol_map = args.symbol_map or (args.raw_dir / "symbol_map.csv")
    client = BitgetPrivateClient(BitgetCredentials.from_env())
    position_history = client.position_history(
        start_time_ms=int(start.timestamp() * 1000),
        end_time_ms=int(end.timestamp() * 1000),
        limit=100,
    )
    result = audit_funding_semantics(
        raw_dir=args.raw_dir,
        symbol_map=symbol_map,
        position_history=position_history,
        order_loader=client.order_history_all,
        max_absolute_error=float(args.max_absolute_error),
        max_relative_error=float(args.max_relative_error),
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        f"funding semantics: {'PASS' if result['passed'] else 'FAIL'} "
        f"({result['cycle_count']} cycle(s), max_abs={result['max_absolute_error']:.10g})"
    )
    for failure in result["hard_failures"]:
        print(f"  FAIL {failure['symbol']} {failure['position_id']}: {failure['detail']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
