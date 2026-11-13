"""Record read-only execution quotes for a future maker-first shadow.

This script never places, cancels or modifies orders. It reads the latest
frozen target book and captures server-timestamped Bitget top-of-book quotes
at a short interval. The resulting JSONL is intended to validate maker-first
fills against real quotes rather than mark-candle proxies.

Run it around the execution window (for example 01:05 UTC) and keep the output
as research evidence. It is not part of the live executor.
"""

from __future__ import annotations

import argparse
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

from atlas20.derivatives.quotes import (  # noqa: E402
    ExecutionQuote,
    QuoteError,
    fetch_execution_quotes,
    require_fresh_quotes,
)
from scripts.plan_live_execution import DEFAULT_SYMBOL_MAP, load_symbol_map  # noqa: E402
from scripts.send_derivatives_signal import DEFAULT_TARGETS_FILE, load_latest_targets  # noqa: E402

DEFAULT_OUTPUT_DIR = Path("reports/derivatives_track_execution_shadow")


def _as_float(value: object) -> float:
    number = float(value)
    if not pd.notna(number):
        raise ValueError("value is not finite")
    return number


def _execution_side(change_weight: float) -> str:
    if change_weight > 0.0:
        return "buy"
    if change_weight < 0.0:
        return "sell"
    return "hold"


def build_shadow_rows(
    book: pd.DataFrame,
    quotes: Mapping[str, ExecutionQuote],
    symbols_by_asset: Mapping[str, str],
    *,
    signal_date: pd.Timestamp,
    execution_hint: pd.Timestamp,
    observation_index: int,
) -> list[dict[str, Any]]:
    """Project one quote snapshot into execution-shadow rows."""
    rows: list[dict[str, Any]] = []
    for _, target in book.iterrows():
        asset = str(target["asset"])
        target_weight = _as_float(target.get("target_weight", 0.0))
        change_weight = _as_float(target.get("change_weight", 0.0))
        if abs(target_weight) <= 1e-15 and abs(change_weight) <= 1e-15:
            continue
        symbol = str(symbols_by_asset.get(asset, "")).upper()
        if not symbol:
            raise QuoteError(f"no Bitget symbol mapping for target asset {asset}")
        quote = quotes.get(symbol)
        if quote is None:
            raise QuoteError(f"no fresh quote for {asset} ({symbol})")
        side = _execution_side(change_weight)
        bid_notional = quote.bid_price * quote.bid_size
        ask_notional = quote.ask_price * quote.ask_size
        top_notional = (
            ask_notional
            if side == "buy"
            else bid_notional
            if side == "sell"
            else min(bid_notional, ask_notional)
        )
        target_notional = target_weight * 1_000.0
        rows.append(
            {
                "observation_index": int(observation_index),
                "signal_date": pd.Timestamp(signal_date).isoformat(),
                "execution_hint": pd.Timestamp(execution_hint).isoformat(),
                "asset": asset,
                "symbol": symbol,
                "side": side,
                "target_weight": target_weight,
                "change_weight": change_weight,
                "target_notional_per_1k": target_notional,
                "last_price": quote.last_price,
                "mark_price": quote.mark_price,
                "bid_price": quote.bid_price,
                "ask_price": quote.ask_price,
                "bid_size": quote.bid_size,
                "ask_size": quote.ask_size,
                "bid_notional": bid_notional,
                "ask_notional": ask_notional,
                "top_of_book_notional": top_notional,
                "top_of_book_to_target_ratio": (
                    top_notional / abs(target_notional) if abs(target_notional) > 0.0 else None
                ),
                "spread_bps": quote.spread_bps,
                "mark_deviation_bps": quote.mark_deviation_bps,
                "age_seconds": quote.age_seconds,
                "observed_at": quote.observed_at.isoformat(),
                "received_at": quote.received_at.isoformat(),
            }
        )
    return rows


def _summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "asset",
                "observations",
                "mean_spread_bps",
                "max_spread_bps",
                "median_top_of_book_notional",
                "median_top_of_book_to_target_ratio",
            ]
        )
    rows: list[dict[str, Any]] = []
    for asset, group in frame.groupby("asset"):
        rows.append(
            {
                "asset": str(asset),
                "observations": int(len(group)),
                "mean_spread_bps": float(group["spread_bps"].mean()),
                "max_spread_bps": float(group["spread_bps"].max()),
                "median_top_of_book_notional": float(
                    group["top_of_book_notional"].median()
                ),
                "median_top_of_book_to_target_ratio": float(
                    group["top_of_book_to_target_ratio"].dropna().median()
                )
                if group["top_of_book_to_target_ratio"].notna().any()
                else None,
            }
        )
    return pd.DataFrame(rows).sort_values("asset")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--observations", type=int, default=5)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--max-quote-age-seconds", type=float, default=120.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.observations < 1:
        parser.error("--observations must be positive")
    if args.interval_seconds < 0.0:
        parser.error("--interval-seconds must be non-negative")
    if args.max_quote_age_seconds <= 0.0:
        parser.error("--max-quote-age-seconds must be positive")

    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    symbols_by_asset = load_symbol_map(args.symbol_map)
    assets = sorted(
        {
            str(row["asset"])
            for _, row in book.iterrows()
            if abs(_as_float(row.get("target_weight", 0.0))) > 1e-15
            or abs(_as_float(row.get("change_weight", 0.0))) > 1e-15
        }
    )
    if not assets:
        raise SystemExit("latest target book has no non-zero target or change")
    symbols = {
        asset: str(symbols_by_asset.get(asset, "")).upper() or asset.upper()
        for asset in assets
    }
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=False) if not output_dir.exists() else None
    quotes_path = output_dir / "quotes.jsonl"
    summary_path = output_dir / "summary.csv"
    manifest_path = output_dir / "manifest.json"
    if not args.overwrite and any(path.exists() for path in (quotes_path, summary_path, manifest_path)):
        raise SystemExit("shadow output already exists; pass --overwrite to replace it")

    session = requests.Session()
    all_rows: list[dict[str, Any]] = []
    for index in range(args.observations):
        quotes = fetch_execution_quotes(
            session,
            symbols.values(),
            timeout_seconds=float(args.timeout_seconds),
        )
        require_fresh_quotes(
            quotes,
            set(symbols.values()),
            max_age_seconds=float(args.max_quote_age_seconds),
        )
        all_rows.extend(
            build_shadow_rows(
                book,
                quotes,
                symbols,
                signal_date=signal_date,
                execution_hint=execution_hint,
                observation_index=index,
            )
        )
        if index + 1 < args.observations:
            time.sleep(max(0.0, float(args.interval_seconds)))

    frame = pd.DataFrame(all_rows)
    _write_jsonl(quotes_path, all_rows)
    _summary(frame).to_csv(summary_path, index=False)
    manifest = {
        "targets_file": str(args.targets_file),
        "symbol_map": str(args.symbol_map),
        "signal_date": signal_date.isoformat(),
        "execution_hint": execution_hint.isoformat(),
        "observations": int(args.observations),
        "interval_seconds": float(args.interval_seconds),
        "max_quote_age_seconds": float(args.max_quote_age_seconds),
        "assets": assets,
        "rows": int(len(all_rows)),
        "read_only": True,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {output_dir} ({len(all_rows)} quote rows; no orders sent)")


if __name__ == "__main__":
    main()
