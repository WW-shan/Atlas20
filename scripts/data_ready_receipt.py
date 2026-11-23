"""Publish and verify the completion boundary between data and signal nodes.

The 08:30 data node and the 08:35 signal node are separate launchd jobs.  A
data refresh can legitimately take longer than five minutes, so the signal
node must not infer completion from the clock alone.  This receipt binds the
completed panel, metadata and Bitget symbol map to the exact READY Top50
pointer that the signal consumes.

The receipt is evidence, not a retry mechanism: a missing or stale receipt
fails the signal node, and the 19:00 monitor surfaces the failure.  It never
rebuilds data and never places an order.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = PROJECT_ROOT / "data" / "derivatives_data_ready.json"
DEFAULT_REPORTS = PROJECT_ROOT / "reports" / "top50_data_readiness"
DEFAULT_PANEL = PROJECT_ROOT / "data" / "processed" / "panel_daily.csv"
DEFAULT_METADATA = PROJECT_ROOT / "data" / "processed" / "metadata.csv"
DEFAULT_SYMBOL_MAP = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "bitget_derivatives"
    / "merged_oos_20261112"
    / "symbol_map.csv"
)
READY_POINTER = "latest_ready.json"


def _utc(value: str | datetime | None = None) -> datetime:
    moment = (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    ) or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload is not an object: {path}")
    return payload


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _current_identity(
    *,
    reports_dir: Path,
    panel_path: Path,
    metadata_path: Path,
    symbol_map_path: Path,
) -> dict[str, object]:
    ready_path = Path(reports_dir) / READY_POINTER
    ready = _read_json(ready_path)
    if ready.get("ready") is not True:
        raise ValueError(f"current Top50 pointer is not READY: {ready_path}")
    if len(ready.get("members") or []) != 50 or len(ready.get("top20") or []) != 20:
        raise ValueError("current Top50 pointer does not contain 50 members and 20 executable names")
    fingerprint = str(ready.get("fingerprint") or "")
    as_of = str(ready.get("as_of") or "")
    if not fingerprint.startswith("sha256:") or not as_of:
        raise ValueError("current Top50 pointer lacks fingerprint or as_of")
    latest_path = Path(reports_dir) / "latest.json"
    latest = _read_json(latest_path)
    if latest != ready:
        raise ValueError("current Top50 READY pointer does not match latest.json")
    inputs = {
        "panel": _sha256(Path(panel_path)),
        "metadata": _sha256(Path(metadata_path)),
        "symbol_map": _sha256(Path(symbol_map_path)),
    }
    if inputs != ready.get("input_files"):
        raise ValueError("current Top50 READY pointer does not commit to the current inputs")
    return {
        "ready_pointer": str(ready_path),
        "ready_sha256": _sha256(ready_path),
        "as_of": as_of,
        "fingerprint": fingerprint,
        "input_files": inputs,
    }


def write_receipt(
    *,
    path: Path,
    reports_dir: Path,
    panel_path: Path,
    metadata_path: Path,
    symbol_map_path: Path,
    now: str | datetime | None = None,
) -> dict[str, object]:
    moment = _utc(now)
    identity = _current_identity(
        reports_dir=reports_dir,
        panel_path=panel_path,
        metadata_path=metadata_path,
        symbol_map_path=symbol_map_path,
    )
    payload: dict[str, object] = {
        "version": 1,
        "ready": True,
        "completed_at": moment.isoformat(),
        "completed_date_utc": moment.date().isoformat(),
        **identity,
    }
    _atomic_json(Path(path), payload)
    return payload


def check_receipt(
    *,
    path: Path,
    reports_dir: Path,
    panel_path: Path,
    metadata_path: Path,
    symbol_map_path: Path,
    now: str | datetime | None = None,
    max_age_minutes: float = 90.0,
) -> dict[str, object]:
    moment = _utc(now)
    receipt = _read_json(Path(path))
    if receipt.get("ready") is not True:
        raise ValueError("data receipt is not READY")
    completed_at = _utc(str(receipt.get("completed_at") or ""))
    if completed_at.date() != moment.date():
        raise ValueError(
            "data receipt is from the previous UTC day "
            f"({completed_at.date()} != {moment.date()})"
        )
    age_minutes = (moment - completed_at).total_seconds() / 60.0
    if age_minutes < -1.0:
        raise ValueError(f"data receipt is in the future ({age_minutes:.1f}m)")
    if age_minutes > float(max_age_minutes):
        raise ValueError(
            f"data receipt is stale ({age_minutes:.1f}m > {max_age_minutes:g}m)"
        )
    identity = _current_identity(
        reports_dir=reports_dir,
        panel_path=panel_path,
        metadata_path=metadata_path,
        symbol_map_path=symbol_map_path,
    )
    for key, value in identity.items():
        if receipt.get(key) != value:
            raise ValueError(f"data receipt {key} does not match current evidence")
    return receipt


def _wait_for_receipt(
    *,
    path: Path,
    reports_dir: Path,
    panel_path: Path,
    metadata_path: Path,
    symbol_map_path: Path,
    max_age_minutes: float,
    wait_seconds: float,
    poll_seconds: float,
) -> dict[str, object]:
    deadline = time.monotonic() + max(0.0, float(wait_seconds))
    last_error = "receipt is missing"
    while True:
        try:
            return check_receipt(
                path=path,
                reports_dir=reports_dir,
                panel_path=panel_path,
                metadata_path=metadata_path,
                symbol_map_path=symbol_map_path,
                max_age_minutes=max_age_minutes,
            )
        except (OSError, ValueError) as exc:
            last_error = str(exc)
        if time.monotonic() >= deadline:
            raise ValueError(f"data node did not complete before the signal deadline: {last_error}")
        time.sleep(min(float(poll_seconds), max(0.1, deadline - time.monotonic())))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check"))
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--now", default=None)
    parser.add_argument("--max-age-minutes", type=float, default=90.0)
    parser.add_argument("--wait-seconds", type=float, default=0.0)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.action == "write":
            receipt = write_receipt(
                path=args.receipt,
                reports_dir=args.reports_dir,
                panel_path=args.panel,
                metadata_path=args.metadata,
                symbol_map_path=args.symbol_map,
                now=args.now,
            )
            print(
                "data ready receipt written: "
                f"as_of={receipt['as_of']} fingerprint={receipt['fingerprint']}"
            )
            return 0
        receipt = _wait_for_receipt(
            path=args.receipt,
            reports_dir=args.reports_dir,
            panel_path=args.panel,
            metadata_path=args.metadata,
            symbol_map_path=args.symbol_map,
            max_age_minutes=args.max_age_minutes,
            wait_seconds=args.wait_seconds,
            poll_seconds=args.poll_seconds,
        )
        print(
            "data ready receipt verified: "
            f"as_of={receipt['as_of']} fingerprint={receipt['fingerprint']}"
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"data ready receipt failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
