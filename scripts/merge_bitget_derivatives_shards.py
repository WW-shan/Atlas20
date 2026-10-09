"""Merge resumable Bitget derivative downloader shards into one raw-data tree.

The downloader keeps one ``state.json`` per shard, so parallel runs cannot
race on a shared state file.  This script performs a strict, idempotent merge
for the backtest loader: candle and funding files are copied, symbol maps are
deduplicated, and conflicting window states are refused instead of hidden.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import pandas as pd


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
    parser.add_argument("--shard", type=Path, action="append", required=True, help="shard directory; repeatable")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-errors", action="store_true")
    args = parser.parse_args()
    manifest = merge_shards(args.shard, args.output_dir, allow_errors=args.allow_errors)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
