"""Merge resumable Bitget derivative downloader shards into one raw-data tree.

The downloader keeps one ``state.json`` per shard, so parallel runs cannot
race on a shared state file.  This script performs a strict, idempotent merge
for the backtest loader: candle and funding files are copied, symbol maps are
deduplicated, and conflicting window states are refused instead of hidden.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil

import pandas as pd

from atlas20.logging_utils import atomic_write_text


_CANDLE_TYPES = {"index", "mark", "market"}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_state(shards: list[Path]) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for shard in shards:
        path = shard / "state.json"
        if not path.exists():
            continue
        for series_key, windows in _load_json(path).items():
            target = merged.setdefault(str(series_key), {})
            for window_key, status in windows.items():
                previous = target.get(window_key)
                if previous is None or previous == status:
                    target[window_key] = status
                    continue
                previous_status = previous.get("status") if isinstance(previous, dict) else None
                status_status = status.get("status") if isinstance(status, dict) else None
                if previous_status == "error" and status_status in {"complete", "missing"}:
                    target[window_key] = status
                elif status_status == "error" and previous_status in {"complete", "missing"}:
                    continue
                else:
                    raise ValueError(
                        f"conflicting state for {series_key} {window_key}: {previous!r} vs {status!r}"
                    )
    return merged


def _merge_frame(paths: list[Path], key: list[str]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths if path.exists()]
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    if not merged.duplicated(key).any():
        return merged
    groups = merged.groupby(key, dropna=False)
    conflicts = []
    for name, group in groups:
        if len(group.drop_duplicates()) > 1:
            conflicts.append(name)
    if conflicts:
        raise ValueError(f"conflicting rows for merge keys {key}: {conflicts[:5]}")
    return merged.drop_duplicates().reset_index(drop=True)


def _copy_files(source: Path, destination: Path) -> int:
    if not source.exists():
        return 0
    count = 0
    for path in sorted(source.iterdir()):
        if not path.is_file():
            continue
        target = destination / path.name
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise ValueError(f"different shard content for {target}")
        if not target.exists():
            shutil.copy2(path, target)
        count += 1
    return count


def _window_coverage(
    frame: pd.DataFrame,
    windows: dict[str, object],
) -> dict[str, object]:
    """Recompute one candle file's coverage from its actual timestamps."""

    times = pd.to_datetime(
        frame["open_time"], utc=True, format="mixed", errors="coerce"
    )
    if times.isna().any():
        raise ValueError("candle file contains an invalid open_time")
    times = pd.DatetimeIndex(times).sort_values()
    if times.has_duplicates:
        raise ValueError("candle file contains duplicate open_time values")

    windows_by_start: dict[pd.Timestamp, object] = {}
    for raw_start, state in windows.items():
        start = pd.Timestamp(raw_start)
        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        else:
            start = start.tz_convert("UTC")
        if start in windows_by_start:
            raise ValueError(f"duplicate coverage window start {start}")
        windows_by_start[start] = state
    starts = sorted(windows_by_start)
    complete_windows = 0
    missing_windows = 0
    partial_windows = 0
    for index, start in enumerate(starts):
        if index + 1 < len(starts):
            end = starts[index + 1]
        else:
            state = windows_by_start[start]
            expected_rows = state.get("expected_rows") if isinstance(state, dict) else None
            if expected_rows is not None:
                if isinstance(expected_rows, bool) or not isinstance(expected_rows, int):
                    raise ValueError(
                        f"invalid expected_rows for candle coverage window {start}"
                    )
                if expected_rows <= 0:
                    raise ValueError(
                        f"non-positive expected_rows for candle coverage window {start}"
                    )
                end = start + pd.Timedelta(hours=expected_rows)
            elif len(times):
                end = pd.Timestamp(times.max()) + pd.Timedelta(hours=1)
            else:
                end = start + pd.Timedelta(days=89)
        if end <= start:
            raise ValueError(f"invalid candle coverage window {start}..{end}")
        observed = times[(times >= start) & (times < end)]
        if len(observed) == 0:
            missing_windows += 1
            continue
        # A contract can list part-way through a downloader window.  Hours
        # before its first actual candle are not missing venue data.  Once the
        # first candle exists, however, a hole through the window is real.
        coverage_start = max(start, pd.Timestamp(observed.min()))
        expected = pd.date_range(coverage_start, end, freq="h", inclusive="left")
        missing = expected.difference(observed)
        if len(missing) == 0 and len(observed) == len(expected):
            complete_windows += 1
        else:
            partial_windows += 1

    gaps = times.to_series().diff().dropna().dt.total_seconds().div(3600.0)
    max_gap_hours = float(gaps.max()) if not gaps.empty else 0.0
    if not math.isfinite(max_gap_hours):
        raise ValueError("candle file produced a non-finite gap")
    window_count = complete_windows + missing_windows + partial_windows
    return {
        "rows": int(len(frame)),
        "first": None if times.empty else times.min().isoformat(),
        "last": None if times.empty else times.max().isoformat(),
        "complete_windows": complete_windows,
        "missing_windows": missing_windows,
        "partial_windows": partial_windows,
        "window_coverage": (
            complete_windows / window_count if window_count else 0.0
        ),
        "max_gap_hours": max_gap_hours,
    }


def reconcile_merged_metadata(output_dir: Path) -> dict[str, object]:
    """Rewrite coverage and merge metadata from the merged files and state.

    Shard coverage is a point-in-time downloader report.  Gap repair can add
    rows to the merged candle files afterwards, so copying that report forever
    leaves the output manifest stale.  This reconciliation is deterministic and
    fails closed when a state series has no corresponding candle file.
    """

    output_dir = Path(output_dir)
    state_path = output_dir / "state.json"
    symbol_map_path = output_dir / "symbol_map.csv"
    candle_dir = output_dir / "candles"
    funding_dir = output_dir / "funding"
    if not state_path.is_file():
        raise FileNotFoundError(f"missing merged state: {state_path}")
    if not symbol_map_path.is_file():
        raise FileNotFoundError(f"missing symbol map: {symbol_map_path}")
    state = _load_json(state_path)
    if not isinstance(state, dict):
        raise ValueError("merged state must be a JSON object")
    symbol_map = pd.read_csv(symbol_map_path)
    if not {"coin_id", "bitget_symbol", "contract_status"}.issubset(
        symbol_map.columns
    ):
        raise ValueError("symbol map is missing coin_id/bitget_symbol/contract_status")
    normal = symbol_map.loc[
        symbol_map["contract_status"].astype(str).str.strip().str.lower().eq("normal")
        & symbol_map["bitget_symbol"].astype(str).str.strip().ne("")
    ]
    coin_ids_by_symbol: dict[str, set[str]] = {}
    for record in normal.to_dict("records"):
        symbol = str(record["bitget_symbol"]).strip().upper()
        coin_id = str(record["coin_id"]).strip()
        if symbol and coin_id:
            coin_ids_by_symbol.setdefault(symbol, set()).add(coin_id)

    existing_path = output_dir / "coverage.json"
    existing_rows: list[dict[str, object]] = []
    if existing_path.is_file():
        payload = _load_json(existing_path)
        if isinstance(payload, list):
            existing_rows = [dict(row) for row in payload if isinstance(row, dict)]
    coin_ids_by_series: dict[tuple[str, str], set[str]] = {}
    for row in existing_rows:
        symbol = str(row.get("bitget_symbol") or "").strip().upper()
        candle_type = str(row.get("candle_type") or "").strip().lower()
        coin_id = str(row.get("coin_id") or "").strip()
        if symbol and candle_type and coin_id:
            coin_ids_by_series.setdefault((symbol, candle_type), set()).add(coin_id)

    coverage_rows: list[dict[str, object]] = []
    seen_series: set[tuple[str, str]] = set()
    for raw_key in sorted(state):
        key = str(raw_key)
        try:
            symbol, candle_type = key.rsplit("_", 1)
        except ValueError as exc:
            raise ValueError(f"invalid state series key: {key}") from exc
        symbol = symbol.strip().upper()
        candle_type = candle_type.strip().lower()
        if candle_type not in _CANDLE_TYPES or not symbol:
            raise ValueError(f"invalid state series key: {key}")
        path = candle_dir / f"{symbol}_{candle_type}.csv"
        if not path.is_file():
            raise ValueError(f"state series has no candle file: {key} -> {path}")
        frame = pd.read_csv(path)
        if "open_time" not in frame.columns:
            raise ValueError(f"candle file has no open_time: {path}")
        windows = state[raw_key]
        if not isinstance(windows, dict) or not windows:
            raise ValueError(f"state series has no coverage windows: {key}")
        metrics = _window_coverage(frame, windows)
        series = (symbol, candle_type)
        seen_series.add(series)
        coin_ids = coin_ids_by_symbol.get(symbol, set()) | coin_ids_by_series.get(
            series, set()
        )
        if not coin_ids:
            raise ValueError(f"candle series has no symbol-map coin_id: {key}")
        for coin_id in sorted(coin_ids):
            coverage_rows.append(
                {
                    "coin_id": coin_id,
                    "bitget_symbol": symbol,
                    "candle_type": candle_type,
                    **metrics,
                }
            )

    candle_files = {
        (path.stem.rsplit("_", 1)[0].upper(), path.stem.rsplit("_", 1)[1].lower())
        for path in candle_dir.glob("*.csv")
        if "_" in path.stem
        and path.stem.rsplit("_", 1)[1].lower() in _CANDLE_TYPES
    }
    unstated = sorted(candle_files.difference(seen_series))
    if unstated:
        raise ValueError(
            "candle file(s) have no state series: "
            + ", ".join(f"{symbol}_{kind}" for symbol, kind in unstated)
        )

    coverage_rows.sort(
        key=lambda row: (
            str(row["bitget_symbol"]),
            str(row["candle_type"]),
            str(row["coin_id"]),
        )
    )
    coverage = pd.DataFrame(coverage_rows)
    atomic_write_text(
        output_dir / "coverage.csv", coverage.to_csv(index=False)
    )
    atomic_write_text(
        output_dir / "coverage.json",
        json.dumps(coverage_rows, indent=2, sort_keys=True, default=str) + "\n",
    )

    error_windows = [
        f"{series_key}:{window_key}"
        for series_key, windows in state.items()
        for window_key, status in windows.items()
        if isinstance(status, dict) and status.get("status") == "error"
    ]
    manifest_path = output_dir / "merge_manifest.json"
    manifest: dict[str, object] = {}
    if manifest_path.is_file():
        payload = _load_json(manifest_path)
        if isinstance(payload, dict):
            manifest = dict(payload)
    manifest.update(
        {
            "state_series": len(state),
            "candle_files": len(list(candle_dir.glob("*.csv"))),
            "funding_files": len(list(funding_dir.glob("*.csv"))),
            "symbol_map_rows": int(len(symbol_map)),
            "coverage_rows": int(len(coverage)),
            "error_windows": error_windows,
            "coverage_source": "reconciled_from_state_and_actual_candles",
        }
    )
    atomic_write_text(
        manifest_path,
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    return manifest


def merge_shards(
    shard_dirs: list[Path],
    output_dir: Path,
    *,
    allow_errors: bool = False,
) -> dict[str, object]:
    if not shard_dirs:
        raise ValueError("at least one shard is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    candle_dir = output_dir / "candles"
    funding_dir = output_dir / "funding"
    candle_dir.mkdir(exist_ok=True)
    funding_dir.mkdir(exist_ok=True)

    for shard in shard_dirs:
        if not shard.is_dir():
            raise ValueError(f"shard is not a directory: {shard}")
        _copy_files(shard / "candles", candle_dir)
        _copy_files(shard / "funding", funding_dir)

    state = _merge_state(shard_dirs)
    error_windows = [
        f"{series_key}:{window_key}"
        for series_key, windows in state.items()
        for window_key, status in windows.items()
        if isinstance(status, dict) and status.get("status") == "error"
    ]
    if error_windows and not allow_errors:
        raise ValueError(
            f"{len(error_windows)} failed download window(s) remain; rerun the downloader or pass "
            "--allow-errors for a deliberately partial merge"
        )
    (output_dir / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    symbol_map = _merge_frame([shard / "symbol_map.csv" for shard in shard_dirs], ["coin_id"])
    if not symbol_map.empty:
        symbol_map.to_csv(output_dir / "symbol_map.csv", index=False)

    coverage = _merge_frame(
        [shard / "coverage.csv" for shard in shard_dirs],
        ["coin_id", "bitget_symbol", "candle_type"],
    )
    if not coverage.empty:
        coverage.to_csv(output_dir / "coverage.csv", index=False)
        coverage_records = coverage.to_dict("records")
        (output_dir / "coverage.json").write_text(
            json.dumps(coverage_records, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )

    contracts: dict[str, object] = {}
    for shard in shard_dirs:
        path = shard / "contracts.json"
        if not path.exists():
            continue
        payload = _load_json(path)
        if isinstance(payload, dict):
            contracts.update(payload)
        elif isinstance(payload, list):
            for contract in payload:
                symbol = contract.get("symbol") if isinstance(contract, dict) else None
                if symbol:
                    contracts[str(symbol)] = contract
    if contracts:
        (output_dir / "contracts.json").write_text(
            json.dumps(contracts, indent=2, sort_keys=True), encoding="utf-8"
        )

    manifest = {
        "shards": [str(path) for path in shard_dirs],
        "state_series": len(state),
        "candle_files": len(list(candle_dir.glob("*.csv"))),
        "funding_files": len(list(funding_dir.glob("*.csv"))),
        "symbol_map_rows": int(len(symbol_map)),
        "coverage_rows": int(len(coverage)),
        "error_windows": error_windows,
        "allow_errors": bool(allow_errors),
    }
    (output_dir / "merge_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shard", type=Path, action="append", help="shard directory; repeatable")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-errors", action="store_true")
    parser.add_argument(
        "--reconcile-only",
        action="store_true",
        help="recompute coverage and merge_manifest from the existing output tree",
    )
    args = parser.parse_args()
    if args.reconcile_only:
        manifest = reconcile_merged_metadata(args.output_dir)
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return
    if not args.shard:
        parser.error("--shard is required unless --reconcile-only is used")
    manifest = merge_shards(args.shard, args.output_dir, allow_errors=args.allow_errors)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
