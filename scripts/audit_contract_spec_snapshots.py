"""Compare Bitget contract-spec snapshots for the live track.

Bitget's public contracts endpoint exposes only the current specification.  We
therefore retain every fetched ``contracts.json`` as a point-in-time snapshot
and compare the fields the backtest quantizes on:

``sizeMultiplier``, ``minTradeUSDT``, ``minTradeNum``, ``fundInterval``,
``pricePlace``, ``priceEndStep`` and ``maxLever``.

The audit cannot invent a snapshot that was never fetched.  It does make the
current OOS reproducible: if a field changed between two retained snapshots,
the run fails instead of silently applying the newer value to the older leg.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

DEFAULT_SNAPSHOT_PATHS = (
    Path("data/raw/bitget_derivatives/contracts.json"),
    Path("data/raw/bitget_derivatives/oos_refresh_20261112/contracts.json"),
    Path("data/raw/bitget_derivatives/merged_oos_20261009/contracts.json"),
    Path("data/raw/bitget_derivatives/merged_oos_20261112/contracts.json"),
)
DEFAULT_CURRENT_SNAPSHOT_GLOB = (
    "data/raw/bitget_derivatives/merged_oos_20261112/"
    "contract_snapshots/contracts_*.json"
)
DEFAULT_SYMBOL_MAP = Path(
    "data/raw/bitget_derivatives/merged_oos_20261112/symbol_map.csv"
)
DEFAULT_OUTPUT = Path("reports/ls45_live_g175/contract_spec_snapshots.json")
SPEC_FIELDS = (
    "sizeMultiplier",
    "minTradeUSDT",
    "minTradeNum",
    "fundInterval",
    "pricePlace",
    "priceEndStep",
    "maxLever",
)


@dataclass(frozen=True)
class Snapshot:
    label: str
    path: Path
    rows: dict[str, dict[str, Any]]
    schema: str
    sha256: str


def _snapshot_rows(payload: object) -> tuple[list[dict[str, Any]], str]:
    """Normalise the contract payload shapes retained by the downloader.

    Historical caches contain either the public API's list response or a
    symbol-keyed dictionary assembled by the merge helpers.  New snapshots use
    a capture wrapper with provenance metadata and a ``contracts`` list.
    """

    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)], "list"
    if isinstance(payload, dict):
        wrapped = payload.get("contracts")
        if isinstance(wrapped, list):
            return [row for row in wrapped if isinstance(row, dict)], "capture_wrapper"
        keyed_rows: list[dict[str, Any]] = []
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            row = dict(value)
            row.setdefault("symbol", key)
            keyed_rows.append(row)
        if keyed_rows:
            return keyed_rows, "symbol_dict"
    raise ValueError("contracts snapshot is not a list, symbol dictionary, or capture wrapper")


def _load_snapshot(path: Path, label: str | None = None) -> Snapshot:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    payload_rows, schema = _snapshot_rows(payload)
    rows: dict[str, dict[str, Any]] = {}
    for row in payload_rows:
        symbol = str(row.get("symbol") or "").upper()
        if symbol:
            rows[symbol] = row
    if not rows:
        raise ValueError(f"contracts snapshot has no symbol rows: {path}")
    return Snapshot(
        label=label or path.parent.name,
        path=path,
        rows=rows,
        schema=schema,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _discover_snapshots(glob_pattern: str) -> list[Path]:
    paths = sorted(Path().glob(glob_pattern), key=lambda item: item.stat().st_mtime)
    return paths


def _default_snapshot_paths() -> list[Path]:
    paths = list(DEFAULT_SNAPSHOT_PATHS)
    for path in _discover_snapshots(DEFAULT_CURRENT_SNAPSHOT_GLOB):
        if path not in paths:
            paths.append(path)
    return paths


def _compare(
    *,
    snapshots: list[Snapshot],
    track_symbols: Iterable[str],
    required_leverage: float = 4.0,
) -> dict[str, Any]:
    symbols = sorted({str(symbol).upper() for symbol in track_symbols if str(symbol)})
    changes: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for symbol in symbols:
        available = [snapshot for snapshot in snapshots if symbol in snapshot.rows]
        if len(available) < 2:
            missing.append(
                {
                    "symbol": symbol,
                    "snapshots": [snapshot.label for snapshot in available],
                }
            )
            continue
        for field in SPEC_FIELDS:
            values = {
                snapshot.label: snapshot.rows[symbol].get(field)
                for snapshot in available
            }
            distinct = {json.dumps(value, sort_keys=True) for value in values.values()}
            if len(distinct) > 1:
                material = True
                reason = f"{field} changed across retained observations"
                if field == "maxLever":
                    try:
                        levers = [float(value) for value in values.values()]
                    except (TypeError, ValueError):
                        levers = []
                    if (
                        len(levers) == len(values)
                        and all(lever >= required_leverage for lever in levers)
                    ):
                        material = False
                        reason = (
                            "all observed values support required "
                            f"{required_leverage:g}x leverage"
                        )
                    else:
                        reason = (
                            "at least one observed value does not support required "
                            f"{required_leverage:g}x leverage or is non-numeric"
                        )
                changes.append(
                    {
                        "symbol": symbol,
                        "field": field,
                        "values": values,
                        "material": material,
                        "reason": reason,
                    }
                )
    material_changes = [change for change in changes if change["material"]]
    return {
        "evidence_scope": (
            "Point-in-time contract observations. Equality across these "
            "snapshots does not by itself prove continuity in intervals for "
            "which no contract snapshot exists."
        ),
        "snapshots": [
            {
                "label": snapshot.label,
                "path": str(snapshot.path),
                "schema": snapshot.schema,
                "sha256": snapshot.sha256,
                "symbols": len(snapshot.rows),
            }
            for snapshot in snapshots
        ],
        "track_symbols": len(symbols),
        "required_leverage": required_leverage,
        "compared_fields": list(SPEC_FIELDS),
        "changes": changes,
        "material_changes": material_changes,
        "missing_snapshot_symbols": missing,
        "passed": len(snapshots) >= 2 and not material_changes and not missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument(
        "--snapshot-glob",
        type=str,
        default=None,
        help="optional glob for an ad-hoc snapshot set",
    )
    parser.add_argument(
        "--snapshot",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="explicit snapshot; may be repeated",
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--required-leverage", type=float, default=4.0)
    args = parser.parse_args(argv)

    if args.required_leverage <= 0.0:
        raise SystemExit("--required-leverage must be positive")

    if args.snapshot:
        snapshots = []
        for item in args.snapshot:
            if "=" not in item:
                raise SystemExit("--snapshot must be LABEL=PATH")
            label, raw_path = item.split("=", 1)
            snapshots.append(_load_snapshot(Path(raw_path), label))
    elif args.snapshot_glob:
        paths = _discover_snapshots(args.snapshot_glob)
        if len(paths) < 2:
            raise SystemExit(
                f"need at least two contracts snapshots matching {args.snapshot_glob}"
            )
        snapshots = [_load_snapshot(path) for path in paths]
    else:
        snapshots = [
            _load_snapshot(path, path.parent.name)
            for path in _default_snapshot_paths()
        ]

    symbol_frame = pd.read_csv(args.symbol_map)
    track_symbols = (
        symbol_frame.loc[
            symbol_frame.get("contract_status", pd.Series(dtype=object))
            .astype(str)
            .str.lower()
            .eq("normal"),
            "bitget_symbol",
        ]
        .dropna()
        .astype(str)
        .str.upper()
        .tolist()
    )
    result = _compare(
        snapshots=snapshots,
        track_symbols=track_symbols,
        required_leverage=float(args.required_leverage),
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"contract spec snapshots: {'PASS' if result['passed'] else 'FAIL'} "
        f"({len(result['snapshots'])} snapshot(s), "
        f"{len(result['material_changes'])} material change(s), "
        f"{len(result['changes'])} observed change(s))"
    )
    for change in result["changes"]:
        marker = "FAIL" if change["material"] else "INFO"
        print(
            f"  {marker} {change['symbol']}.{change['field']}: "
            f"{change['values']} — {change['reason']}"
        )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
