"""Repair interior hourly gaps in a cached Bitget mark tree.

The historical cache was produced by an older pager that dropped one bar at
some 100-row boundaries.  Re-fetching every 89-day window is both expensive and
unnecessary; this tool identifies the exact missing runs and asks Bitget for a
small window around each run using the current, gap-safe paginator.

Only interior gaps between a symbol's first and last observed bars are
considered.  Pre-listing and post-delisting periods are not fabricated.  A
failed fetch leaves the existing file untouched.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.bitget import BitgetClient  # noqa: E402
from atlas20.logging_utils import atomic_write_text  # noqa: E402
from scripts.download_bitget_derivatives_data import (  # noqa: E402
    _merge_candles,
    _write_csv_atomic,
)
from scripts.merge_bitget_derivatives_shards import (  # noqa: E402
    reconcile_merged_metadata,
)


@dataclass(frozen=True)
class RepairResult:
    symbol: str
    missing_before: int
    missing_after: int
    fetched_rows: int
    windows: int
    error: str | None = None


def _times(frame: pd.DataFrame) -> pd.DatetimeIndex:
    if frame.empty or "open_time" not in frame.columns:
        return pd.DatetimeIndex([])
    values = pd.to_datetime(frame["open_time"], utc=True, format="mixed", errors="coerce")
    return pd.DatetimeIndex(values.dropna().drop_duplicates().sort_values())


def missing_hour_runs(
    frame: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return contiguous missing-hour runs inside a symbol's observed life."""

    times = _times(frame)
    if times.empty:
        return []
    first = max(pd.Timestamp(start).tz_convert("UTC") if pd.Timestamp(start).tzinfo else pd.Timestamp(start).tz_localize("UTC"), times.min())
    last_observed = times.max()
    end_exclusive = min(
        pd.Timestamp(end).tz_convert("UTC") if pd.Timestamp(end).tzinfo else pd.Timestamp(end).tz_localize("UTC"),
        last_observed + pd.Timedelta(hours=1),
    )
    if end_exclusive <= first:
        return []
    expected = pd.date_range(first, end_exclusive, freq="h", inclusive="left")
    missing = expected.difference(times)
    if missing.empty:
        return []
    runs: list[list[pd.Timestamp]] = [[pd.Timestamp(missing[0])]]
    for stamp in missing[1:]:
        current = pd.Timestamp(stamp)
        if current - runs[-1][-1] == pd.Timedelta(hours=1):
            runs[-1].append(current)
        else:
            runs.append([current])
    return [(run[0], run[-1]) for run in runs]


def repair_symbol(
    raw_dir: Path,
    *,
    symbol: str,
    client: Any,
    start: pd.Timestamp,
    end: pd.Timestamp,
    dry_run: bool = False,
    flush_every: int = 50,
) -> RepairResult:
    """Fetch and merge only the missing windows for one symbol."""

    if flush_every < 1:
        raise ValueError("flush_every must be at least 1")
    path = Path(raw_dir) / "candles" / f"{symbol.upper()}_mark.csv"
    if not path.is_file():
        return RepairResult(symbol.upper(), 0, 0, 0, 0, error=f"missing mark file: {path}")
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return RepairResult(symbol.upper(), 0, 0, 0, error=f"unreadable mark file: {exc}")
    runs = missing_hour_runs(frame, start=start, end=end)
    before = sum(int((run_end - run_start) / pd.Timedelta(hours=1)) + 1 for run_start, run_end in runs)
    if dry_run:
        return RepairResult(symbol.upper(), before, before, 0, len(runs))

    merged = frame
    pending: list[pd.DataFrame] = []
    fetched_rows = 0
    windows = 0
    errors: list[str] = []

    def flush_pending() -> None:
        nonlocal merged
        if not pending:
            return
        batch = pd.concat(pending, ignore_index=True)
        pending.clear()
        merged = _merge_candles(merged, batch)
        _write_csv_atomic(merged, path)

    try:
        for run_start, run_end in runs:
            # A one-hour request is less likely to hide another boundary
            # artifact; the current paginator handles the window exactly.
            fetch_start = run_start - pd.Timedelta(hours=1)
            fetch_end = run_end + pd.Timedelta(hours=2)
            windows += 1
            try:
                fetched = client.fetch_history_candles(
                    symbol.upper(),
                    "mark",
                    fetch_start,
                    fetch_end,
                )
            except Exception as exc:  # noqa: BLE001 - continue with other gaps
                errors.append(f"{run_start}: {exc}")
                continue
            if fetched.empty:
                continue
            fetched_rows += len(fetched)
            pending.append(fetched)
            if len(pending) >= flush_every:
                flush_pending()
    except Exception as exc:  # noqa: BLE001 - retain every already merged bar
        flush_pending()
        remaining = missing_hour_runs(merged, start=start, end=end)
        after = sum(
            int((run_end - run_start) / pd.Timedelta(hours=1)) + 1
            for run_start, run_end in remaining
        )
        return RepairResult(
            symbol.upper(),
            before,
            after,
            fetched_rows,
            windows,
            error=str(exc),
        )

    flush_pending()
    remaining = missing_hour_runs(merged, start=start, end=end)
    after = sum(int((run_end - run_start) / pd.Timedelta(hours=1)) + 1 for run_start, run_end in remaining)
    return RepairResult(
        symbol.upper(),
        before,
        after,
        fetched_rows,
        windows,
        error="; ".join(errors[:3]) if errors else None,
    )


def _select_symbols(raw_dir: Path, requested: set[str]) -> list[str]:
    symbol_map = raw_dir / "symbol_map.csv"
    symbols: list[str] = []
    if symbol_map.is_file():
        try:
            frame = pd.read_csv(symbol_map)
            for record in frame.to_dict("records"):
                coin_id = str(record.get("coin_id") or "").strip().lower()
                symbol = str(record.get("bitget_symbol") or "").strip().upper()
                status = str(record.get("contract_status") or "normal").strip().lower()
                if symbol and status == "normal" and (
                    not requested or coin_id in requested or symbol.lower() in requested
                ):
                    symbols.append(symbol)
        except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
            pass
    if not symbols:
        for path in sorted((raw_dir / "candles").glob("*_mark.csv")):
            symbol = path.stem.removesuffix("_mark").upper()
            if not requested or symbol.lower() in requested:
                symbols.append(symbol)
    return sorted(set(symbols))


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2026-09-21")
    parser.add_argument("--symbols", default="", help="comma-separated coin ids or symbols")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--rate-limit-seconds", type=float, default=0.2)
    parser.add_argument("--flush-every", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    raw_dir = Path(args.raw_dir).resolve()
    if not raw_dir.is_dir():
        raise SystemExit(f"raw directory does not exist: {raw_dir}")
    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    requested = {
        value.strip().lower()
        for value in str(args.symbols).split(",")
        if value.strip()
    }
    symbols = _select_symbols(raw_dir, requested)
    if not symbols:
        raise SystemExit("no symbols selected")

    def run_one(symbol: str) -> RepairResult:
        client = BitgetClient(
            max_retries=8,
            retry_backoff_seconds=2.0,
            rate_limit_seconds=float(args.rate_limit_seconds),
        )
        return repair_symbol(
            raw_dir,
            symbol=symbol,
            client=client,
            start=start,
            end=end,
            dry_run=bool(args.dry_run),
            flush_every=int(args.flush_every),
        )

    results: list[RepairResult] = []
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as pool:
        futures = {pool.submit(run_one, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{result.symbol}: {result.missing_before} missing -> "
                f"{result.missing_after}, {result.fetched_rows} rows, "
                f"{result.windows} windows"
                + (f", error={result.error}" if result.error else ""),
                flush=True,
            )
    results.sort(key=lambda item: item.symbol)
    report = {
        "raw_dir": str(raw_dir),
        "start": str(start),
        "end": str(end),
        "dry_run": bool(args.dry_run),
        "symbols": len(results),
        "missing_before": sum(item.missing_before for item in results),
        "missing_after": sum(item.missing_after for item in results),
        "fetched_rows": sum(item.fetched_rows for item in results),
        "windows": sum(item.windows for item in results),
        "flush_every": int(args.flush_every),
        "errors": [
            {"symbol": item.symbol, "error": item.error}
            for item in results
            if item.error
        ],
        "results": [item.__dict__ for item in results],
    }
    if not args.dry_run:
        # Gap repair changes candle files after the downloader wrote their
        # point-in-time coverage report.  Recompute the merged metadata in the
        # same process so a later signal rebuild cannot consume stale coverage,
        # fingerprints or row counts.
        report["metadata_manifest"] = reconcile_merged_metadata(raw_dir)
        atomic_write_text(
            raw_dir / "gap_repair.json",
            json.dumps(report, indent=2, sort_keys=True),
        )
    print(json.dumps({key: report[key] for key in ("symbols", "missing_before", "missing_after", "fetched_rows", "windows", "errors")}, indent=2))
    return 1 if report["missing_after"] or report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
