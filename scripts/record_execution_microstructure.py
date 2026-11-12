"""Record read-only Bitget order-book snapshots around an execution study.

The collector sizes the latest target ledger's non-zero change legs from a
reference equity, walks visible depth for an immediate marketable order, and
stores the raw public books plus derived impact metrics. It never places,
cancels or modifies an order and never reads private account credentials.

An off-window sample is still useful for liquidity diagnostics, but it is not
evidence that a rebalance filled at that time.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.orderbook import (  # noqa: E402
    OrderBookError,
    OrderBookSnapshot,
    fetch_order_books,
    require_fresh_order_books,
    walk_order_book,
)
from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    load_symbol_map,
)
from scripts.send_derivatives_signal import (  # noqa: E402
    DEFAULT_TARGETS_FILE,
    load_latest_targets,
)

DEFAULT_OUTPUT_DIR = Path("reports/derivatives_track_execution_microstructure")
DEFAULT_EQUITY = 500.0


def _finite_float(value: object) -> float:
    number = float(value)
    if not pd.notna(number) or number in (float("inf"), float("-inf")):
        raise ValueError("value must be finite")
    return number


def _side(change_weight: float) -> str:
    return "buy" if change_weight > 0.0 else "sell"


def select_execution_legs(
    book: pd.DataFrame,
    symbols_by_asset: Mapping[str, str],
    *,
    equity: float,
) -> list[dict[str, Any]]:
    """Select and size the target ledger's non-zero change legs."""
    capital = _finite_float(equity)
    if capital <= 0.0:
        raise ValueError("equity must be positive")
    legs: list[dict[str, Any]] = []
    for _, target in book.iterrows():
        asset = str(target["asset"])
        target_weight = _finite_float(target.get("target_weight", 0.0))
        change_weight = _finite_float(target.get("change_weight", 0.0))
        if abs(change_weight) <= 1e-15:
            continue
        symbol = str(symbols_by_asset.get(asset, "")).strip().upper()
        if not symbol:
            raise ValueError(f"no Bitget symbol mapping for target asset {asset}")
        legs.append(
            {
                "asset": asset,
                "symbol": symbol,
                "side": _side(change_weight),
                "target_weight": target_weight,
                "change_weight": change_weight,
                "target_notional": target_weight * capital,
                "change_notional": change_weight * capital,
                "action": str(target.get("action", "")),
            }
        )
    return legs


def _depth_within_bps(book: OrderBookSnapshot, side: str, bps: float) -> float:
    if side == "buy":
        best = book.asks[0].price
        return sum(level.notional for level in book.asks if level.price <= best * (1.0 + bps / 10_000.0))
    best = book.bids[0].price
    return sum(level.notional for level in book.bids if level.price >= best * (1.0 - bps / 10_000.0))


def build_microstructure_rows(
    legs: list[dict[str, Any]],
    books: Mapping[str, OrderBookSnapshot],
    *,
    observation_index: int,
    execution_hint: pd.Timestamp,
) -> list[dict[str, Any]]:
    """Project one public book snapshot into executable-depth rows."""
    rows: list[dict[str, Any]] = []
    for leg in legs:
        symbol = str(leg["symbol"])
        book = books.get(symbol)
        if book is None:
            raise OrderBookError(f"no live order book for {leg['asset']} ({symbol})")
        side = str(leg["side"])
        requested = abs(_finite_float(leg["change_notional"]))
        fill = walk_order_book(book, side, requested)
        spread_bps = (book.asks[0].price - book.bids[0].price) / (
            (book.asks[0].price + book.bids[0].price) / 2.0
        ) * 10_000.0
        top_notional = book.asks[0].notional if side == "buy" else book.bids[0].notional
        depth_10 = _depth_within_bps(book, side, 10.0)
        depth_25 = _depth_within_bps(book, side, 25.0)
        rows.append(
            {
                "observation_index": int(observation_index),
                "execution_hint": pd.Timestamp(execution_hint).isoformat(),
                "asset": leg["asset"],
                "symbol": symbol,
                "side": side,
                "target_weight": float(leg["target_weight"]),
                "change_weight": float(leg["change_weight"]),
                "target_notional": float(leg.get("target_notional", 0.0)),
                "change_notional": float(leg["change_notional"]),
                "requested_notional": requested,
                "filled_notional": fill.filled_notional,
                "unfilled_notional": fill.unfilled_notional,
                "fill_ratio": fill.filled_notional / requested,
                "average_price": fill.average_price,
                "best_price": fill.best_price,
                "levels_consumed": fill.levels_consumed,
                "impact_bps": fill.impact_bps,
                "spread_bps": spread_bps,
                "top_of_book_notional": top_notional,
                "top_of_book_to_order_ratio": top_notional / requested,
                "depth_10bps_notional": depth_10,
                "depth_10bps_to_order_ratio": depth_10 / requested,
                "depth_25bps_notional": depth_25,
                "depth_25bps_to_order_ratio": depth_25 / requested,
                "observed_at": book.observed_at.isoformat(),
                "received_at": book.received_at.isoformat(),
                "book_age_seconds": book.age_seconds,
                "bids": [[level.price, level.size] for level in book.bids],
                "asks": [[level.price, level.size] for level in book.asks],
            }
        )
    return rows


def _summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "asset",
        "symbol",
        "observations",
        "median_spread_bps",
        "p95_spread_bps",
        "median_impact_bps",
        "p95_impact_bps",
        "max_impact_bps",
        "min_fill_ratio",
        "median_top_of_book_to_order_ratio",
        "median_depth_25bps_to_order_ratio",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for (asset, symbol), group in frame.groupby(["asset", "symbol"], sort=True):
        rows.append(
            {
                "asset": str(asset),
                "symbol": str(symbol),
                "observations": int(len(group)),
                "median_spread_bps": float(group["spread_bps"].median()),
                "p95_spread_bps": float(group["spread_bps"].quantile(0.95)),
                "median_impact_bps": float(group["impact_bps"].median()),
                "p95_impact_bps": float(group["impact_bps"].quantile(0.95)),
                "max_impact_bps": float(group["impact_bps"].max()),
                "min_fill_ratio": float(group["fill_ratio"].min()),
                "median_top_of_book_to_order_ratio": float(
                    group["top_of_book_to_order_ratio"].median()
                ),
                "median_depth_25bps_to_order_ratio": float(
                    group["depth_25bps_to_order_ratio"].median()
                ),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _report(summary: pd.DataFrame, *, observations: int, equity: float) -> str:
    lines = [
        "# Execution microstructure sample",
        "",
        f"- equity reference: **{equity:.2f} USDT**",
        f"- requested snapshots: **{observations}**",
        "- read-only: **yes**; orders sent: **no**",
        "",
        "| asset | symbol | obs | median spread bps | p95 spread bps | median impact bps | p95 impact bps | max impact bps | min fill ratio | median depth25/order |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.asset} | {row.symbol} | {row.observations} | "
            f"{row.median_spread_bps:.4f} | {row.p95_spread_bps:.4f} | "
            f"{row.median_impact_bps:.4f} | {row.p95_impact_bps:.4f} | "
            f"{row.max_impact_bps:.4f} | {row.min_fill_ratio:.4f} | "
            f"{row.median_depth_25bps_to_order_ratio:.4f} |"
        )
    lines.extend(
        [
            "",
            "The impact estimate walks the public visible book for an immediate order.",
            "It excludes fees, queue position, hidden liquidity, partial fills, rejections and latency.",
            "An off-window sample does not prove execution quality at the actual rebalance.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--equity", type=float, default=DEFAULT_EQUITY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--observations", type=int, default=12)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--max-book-age-seconds", type=float, default=120.0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.observations < 1:
        parser.error("--observations must be positive")
    if args.interval_seconds < 0.0:
        parser.error("--interval-seconds must be non-negative")
    if args.max_book_age_seconds <= 0.0:
        parser.error("--max-book-age-seconds must be positive")
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.equity <= 0.0:
        parser.error("--equity must be positive")

    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    symbols_by_asset = load_symbol_map(args.symbol_map)
    legs = select_execution_legs(book, symbols_by_asset, equity=float(args.equity))
    if not legs:
        raise SystemExit("latest target book has no non-zero change")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshots_path = output_dir / "orderbooks.jsonl"
    summary_path = output_dir / "summary.csv"
    report_path = output_dir / "report.md"
    errors_path = output_dir / "errors.jsonl"
    manifest_path = output_dir / "manifest.json"
    existing = [path for path in (snapshots_path, summary_path, report_path, errors_path, manifest_path) if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit("microstructure output already exists; pass --overwrite to replace it")

    session = requests.Session()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    completed = 0
    symbols = sorted({str(leg["symbol"]) for leg in legs})
    for index in range(args.observations):
        try:
            books = fetch_order_books(
                session,
                symbols,
                limit=int(args.limit),
                timeout_seconds=float(args.timeout_seconds),
            )
            require_fresh_order_books(
                books,
                symbols,
                max_age_seconds=float(args.max_book_age_seconds),
            )
            rows.extend(
                build_microstructure_rows(
                    legs,
                    books,
                    observation_index=index,
                    execution_hint=execution_hint,
                )
            )
            completed += 1
        except OrderBookError as exc:
            errors.append(
                {
                    "observation_index": index,
                    "received_at": pd.Timestamp.now(tz="UTC").isoformat(),
                    "error": str(exc),
                }
            )
        if index + 1 < args.observations:
            time.sleep(max(0.0, float(args.interval_seconds)))

    frame = pd.DataFrame(rows)
    summary = _summary(frame)
    _write_jsonl(snapshots_path, rows)
    _write_jsonl(errors_path, errors)
    summary.to_csv(summary_path, index=False)
    report_path.write_text(
        _report(summary, observations=completed, equity=float(args.equity)),
        encoding="utf-8",
    )
    manifest = {
        "targets_file": str(args.targets_file),
        "targets_sha256": _sha256(args.targets_file),
        "symbol_map": str(args.symbol_map),
        "symbol_map_sha256": _sha256(args.symbol_map),
        "signal_date": signal_date.isoformat(),
        "execution_hint": execution_hint.isoformat(),
        "equity_reference": float(args.equity),
        "requested_observations": int(args.observations),
        "completed_observations": int(completed),
        "interval_seconds": float(args.interval_seconds),
        "limit": int(args.limit),
        "symbols": symbols,
        "legs": legs,
        "rows": int(len(rows)),
        "errors": int(len(errors)),
        "read_only": True,
        "orders_sent": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {output_dir} ({completed}/{args.observations} snapshots; "
        f"{len(rows)} rows; no orders sent)"
    )


if __name__ == "__main__":
    main()
