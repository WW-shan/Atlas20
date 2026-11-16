"""Refresh the LS104 data/signal chain without placing orders.

This job exists because the daily execution chain is intentionally bounded to
the T+1 trading window.  Funding and mark candles continue to age outside that
window, so a read-only refresh must rebuild the frozen inputs before the next
audit can require them to be fresh.

The refresh acquires the same process lock as the executor.  If an execution
is in progress, the timer skips this fire; it never waits indefinitely and it
never calls the executor or Telegram sender.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

import pandas as pd
from filelock import FileLock, Timeout

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = PROJECT_ROOT / "data" / "derivatives_execution.lock"
DEFAULT_RECEIPT = PROJECT_ROOT / "reports" / "ls45_live_g175_live" / "prepared.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "reports" / "ls45_live_g175" / "manifest.json"
DEFAULT_PANEL = PROJECT_ROOT / "data" / "processed" / "panel_daily.csv"
DEFAULT_PANEL_LOCK = PROJECT_ROOT / "data" / ".daily-refresh.lock"
AUDIT_FILES = (
    PROJECT_ROOT / "reports" / "ls45_live_g175" / "data_audit.json",
    PROJECT_ROOT / "reports" / "ls45_live_g175_live" / "signal_equivalence.json",
    PROJECT_ROOT / "reports" / "ls45_live_g175_live" / "venue_symbol_audit.json",
    PROJECT_ROOT / "reports" / "ls45_live_g175" / "contract_spec_snapshots.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_prepare_receipt(
    *,
    project_root: Path,
    manifest_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    project_root = Path(project_root).resolve()
    receipt = {
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "track": "ls104-g175-m090",
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "targets_sha256": manifest.get("targets_sha256"),
        "data_fingerprint": manifest.get("data_fingerprint"),
        "fill_price_source": manifest.get("fill_price_source"),
        "market_fill_fingerprint": manifest.get("market_fill_fingerprint"),
        "execution_price_model": manifest.get("execution_price_model"),
        "signal_end_date": manifest.get("signal_end_date"),
        "last_mark": manifest.get("last_mark"),
        "audit_files": {
            str(path.relative_to(project_root)): _sha256(path)
            for path in AUDIT_FILES
            if path.is_file()
        },
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(receipt_path)
    return receipt


def build_refresh_commands(
    *,
    make_command: str = "/usr/bin/make",
    project_root: Path = PROJECT_ROOT,
) -> list[list[str]]:
    """Return the exact LS104 refresh/audit sequence.

    ``derivatives-ls104-signal`` rebuilds the manifest as well as the target
    CSV, so refreshing marks or funding can never leave the executor with an
    old fingerprint under a new raw tree.  The sequence deliberately contains
    no execution or notification target.
    """

    return [
        [make_command, "derivatives-live-data", "derivatives-ls104-signal"],
        [make_command, "audit-data-chain"],
        [make_command, "audit-data-ls104"],
        [make_command, "audit-symbols-ls104"],
        [make_command, "audit-contract-specs-ls104"],
        [make_command, "audit-signal-ls104"],
    ]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="project checkout containing the Makefile",
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=None,
        help="shared execution lock (default: <project-root>/data/derivatives_execution.lock)",
    )
    parser.add_argument(
        "--make-command",
        default=shutil.which("make") or "/usr/bin/make",
        help="make executable to invoke",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the commands without acquiring a lock or executing them",
    )
    parser.add_argument(
        "--receipt-out",
        type=Path,
        default=DEFAULT_RECEIPT,
        help="write a successful-refresh receipt after every command passes",
    )
    parser.add_argument(
        "--check-receipt",
        action="store_true",
        help="validate the receipt against the current manifest and exit without running make",
    )
    parser.add_argument(
        "--check-lock",
        action="store_true",
        help="exit 0 when the execution lock is free, 3 when it is held",
    )
    parser.add_argument(
        "--skip-if-fresh-receipt",
        action="store_true",
        help="skip the whole refresh when the existing receipt is still valid",
    )
    parser.add_argument(
        "--pre-execution",
        action="store_true",
        help="refuse to start a long prepare after the pre-execution cut-off",
    )
    parser.add_argument(
        "--panel-wait-seconds",
        type=float,
        default=900.0,
        help="wait for the daily panel refresh lock and a current panel before starting",
    )
    parser.add_argument(
        "--execution-lock-wait-seconds",
        type=float,
        default=60.0,
        help="wait this long for an in-flight prepare before skipping",
    )
    parser.add_argument(
        "--panel",
        type=Path,
        default=DEFAULT_PANEL,
    )
    parser.add_argument(
        "--panel-lock",
        type=Path,
        default=DEFAULT_PANEL_LOCK,
    )
    parser.add_argument(
        "--skip-panel-wait",
        action="store_true",
        help="skip the daily-refresh lock/current-panel wait (tests only)",
    )
    parser.add_argument(
        "--latest-start-utc",
        default="00:50",
        help="latest UTC HH:MM at which --pre-execution may start",
    )
    parser.add_argument(
        "--max-age-minutes",
        type=float,
        default=30.0,
        help="maximum receipt age accepted by --check-receipt",
    )
    return parser.parse_args(argv)


def _pre_execution_too_late(args: argparse.Namespace) -> bool:
    if not args.pre_execution:
        return False
    try:
        latest_hour, latest_minute = (
            int(part) for part in str(args.latest_start_utc).split(":", 1)
        )
    except ValueError as exc:
        raise SystemExit(f"--latest-start-utc must be HH:MM: {exc}") from exc
    latest = datetime.now(timezone.utc).replace(
        hour=latest_hour, minute=latest_minute, second=0, microsecond=0
    )
    return datetime.now(timezone.utc) >= latest


def _panel_last_day(path: Path) -> object:
    frame = pd.read_csv(path, usecols=["date"])
    if frame.empty:
        return None
    values = pd.to_datetime(frame["date"], utc=True, errors="coerce").dropna()
    if values.empty:
        return None
    return pd.Timestamp(values.max()).date()


def wait_for_current_panel(
    *,
    panel_path: Path,
    lock_path: Path,
    wait_seconds: float,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Wait out a running daily refresh and require the latest completed day."""

    if wait_seconds < 0.0:
        return False, "panel wait must be non-negative"
    moment = now or datetime.now(timezone.utc)
    expected = moment.date() - pd.Timedelta(days=1).to_pytimedelta()
    deadline = time.monotonic() + float(wait_seconds)
    while True:
        try:
            with FileLock(str(lock_path), timeout=1.0):
                pass
        except Timeout:
            if time.monotonic() >= deadline:
                return False, f"daily refresh lock stayed busy for {wait_seconds:g}s"
            time.sleep(min(5.0, max(0.5, deadline - time.monotonic())))
            continue
        if panel_path.is_file():
            latest = _panel_last_day(panel_path)
            if latest is not None and latest >= expected:
                return True, f"panel carries {latest}"
        if time.monotonic() >= deadline:
            return False, (f"panel did not reach {expected} within {wait_seconds:g}s")
        time.sleep(min(10.0, max(0.5, deadline - time.monotonic())))


def check_prepare_receipt(
    *,
    receipt_path: Path,
    manifest_path: Path,
    max_age_minutes: float,
    project_root: Path = PROJECT_ROOT,
) -> tuple[bool, str]:
    """Return whether a prepare receipt still proves the current frozen book."""

    if max_age_minutes < 0.0:
        return False, "max age must be non-negative"
    if not receipt_path.is_file():
        return False, f"prepare receipt missing: {receipt_path}"
    if not manifest_path.is_file():
        return False, f"manifest missing: {manifest_path}"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"prepare receipt unreadable: {exc}"
    if not isinstance(receipt, dict):
        return False, "prepare receipt is not a JSON object"
    try:
        prepared_at = datetime.fromisoformat(
            str(receipt.get("prepared_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        return False, "prepare receipt has no valid prepared_at"
    if prepared_at.tzinfo is None:
        prepared_at = prepared_at.replace(tzinfo=timezone.utc)
    age_minutes = (
        datetime.now(timezone.utc) - prepared_at.astimezone(timezone.utc)
    ).total_seconds() / 60.0
    if age_minutes < -1.0:
        return False, f"prepare receipt is in the future ({age_minutes:.1f}m)"
    if age_minutes > float(max_age_minutes):
        return False, (
            f"prepare receipt is stale ({age_minutes:.1f}m > "
            f"{float(max_age_minutes):g}m)"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in (
        "targets_sha256",
        "data_fingerprint",
        "fill_price_source",
        "market_fill_fingerprint",
        "execution_price_model",
        "signal_end_date",
    ):
        if receipt.get(key) != manifest.get(key):
            return False, f"prepare receipt {key} does not match manifest"
    if receipt.get("manifest_sha256") != _sha256(manifest_path):
        return False, "prepare receipt manifest hash does not match"
    for name, digest in dict(receipt.get("audit_files") or {}).items():
        path = Path(project_root) / name
        if not path.is_file() or _sha256(path) != str(digest):
            return False, f"audit file changed after prepare: {name}"
    return True, f"prepare receipt is valid ({age_minutes:.1f}m old)"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = Path(args.project_root).expanduser().resolve()
    make_command = str(args.make_command)
    lock_path = (
        Path(args.lock_file).expanduser()
        if args.lock_file is not None
        else project_root / "data" / "derivatives_execution.lock"
    )
    commands = build_refresh_commands(
        make_command=make_command,
        project_root=project_root,
    )

    if args.check_receipt:
        valid, reason = check_prepare_receipt(
            receipt_path=Path(args.receipt_out),
            manifest_path=project_root / "reports" / "ls45_live_g175" / "manifest.json",
            max_age_minutes=float(args.max_age_minutes),
            project_root=project_root,
        )
        print(reason)
        return 0 if valid else 3

    if args.check_lock:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print(f"execution lock is busy: {lock_path}")
                return 3
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        print(f"execution lock is free: {lock_path}")
        return 0

    if args.dry_run:
        for command in commands:
            print(" ".join(command))
        return 0

    # A fresh receipt must short-circuit before the pre-execution cut-off.
    # In particular the 08:55 Beijing catch-up fire is after 00:50 UTC; it
    # should still no-op when 08:35 already produced a valid receipt.
    if args.skip_if_fresh_receipt:
        valid, reason = check_prepare_receipt(
            receipt_path=Path(args.receipt_out),
            manifest_path=project_root / "reports" / "ls45_live_g175" / "manifest.json",
            max_age_minutes=float(args.max_age_minutes),
            project_root=project_root,
        )
        if valid:
            print(f"derivatives refresh skipped: {reason}")
            return 0

    if _pre_execution_too_late(args):
        print(
            "derivatives prepare skipped: past the pre-execution cut-off "
            f"{args.latest_start_utc} UTC"
        )
        return 0

    if not args.skip_panel_wait:
        panel_ok, panel_reason = wait_for_current_panel(
            panel_path=Path(args.panel),
            lock_path=Path(args.panel_lock),
            wait_seconds=float(args.panel_wait_seconds),
        )
        if not panel_ok:
            print(f"derivatives refresh stopped: {panel_reason}", file=sys.stderr)
            return 3
        print(panel_reason)
        if _pre_execution_too_late(args):
            print(
                "derivatives prepare stopped after the panel wait: past the "
                f"pre-execution cut-off {args.latest_start_utc} UTC"
            )
            return 0

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        lock_deadline = time.monotonic() + float(args.execution_lock_wait_seconds)
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= lock_deadline:
                    print(
                        f"derivatives refresh skipped: execution lock is busy: {lock_path}"
                    )
                    return 0
                time.sleep(1.0)
        if args.skip_if_fresh_receipt:
            valid, reason = check_prepare_receipt(
                receipt_path=Path(args.receipt_out),
                manifest_path=project_root
                / "reports"
                / "ls45_live_g175"
                / "manifest.json",
                max_age_minutes=float(args.max_age_minutes),
                project_root=project_root,
            )
            if valid:
                print(f"derivatives refresh skipped: {reason}")
                return 0
        try:
            for command in commands:
                print("running: " + " ".join(command), flush=True)
                completed = subprocess.run(
                    command,
                    cwd=project_root,
                    check=False,
                )
                if completed.returncode != 0:
                    print(
                        f"derivatives refresh stopped: command exited {completed.returncode}",
                        file=sys.stderr,
                    )
                    return int(completed.returncode)
            manifest_path = (
                project_root / "reports" / "ls45_live_g175" / "manifest.json"
            )
            receipt = write_prepare_receipt(
                project_root=project_root,
                manifest_path=manifest_path,
                receipt_path=Path(args.receipt_out),
            )
            print(
                "prepare receipt written: "
                f"{args.receipt_out} targets={receipt['targets_sha256']}"
            )
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
