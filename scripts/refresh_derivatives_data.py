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
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
from filelock import FileLock, Timeout

from atlas20.derivatives.data_audit import required_last_mark_time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = PROJECT_ROOT / "data" / "derivatives_execution.lock"
DEFAULT_RECEIPT = PROJECT_ROOT / "reports" / "ls45_live_g175_live" / "prepared.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "reports" / "ls45_live_g175" / "manifest.json"
DEFAULT_PANEL = PROJECT_ROOT / "data" / "processed" / "panel_daily.csv"
DEFAULT_PANEL_LOCK = PROJECT_ROOT / "data" / ".daily-refresh.lock"
AUDIT_FILE_NAMES = (
    "reports/ls45_live_g175/data_audit.json",
    "reports/ls45_live_g175_live/signal_equivalence.json",
    "reports/ls45_live_g175_live/venue_symbol_audit.json",
    "reports/ls45_live_g175/contract_spec_snapshots.json",
)
AUDIT_FILES = tuple(PROJECT_ROOT / name for name in AUDIT_FILE_NAMES)
RECEIPT_MANIFEST_FIELDS = (
    "targets_sha256",
    "data_fingerprint",
    "fill_price_source",
    "market_fill_fingerprint",
    "execution_price_model",
    "signal_end_date",
    "last_mark",
)
RECEIPT_TRACK = "ls104-g175-m090"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readiness_commitment_issue(
    manifest: dict[str, object], *, project_root: Path
) -> str | None:
    """Verify that the current READY pointer is the one bound by the manifest."""

    executable = manifest.get("executable_universe")
    if executable is None:
        return None
    if not isinstance(executable, dict):
        return "manifest executable_universe is not an object"
    fingerprint = str(executable.get("fingerprint") or "")
    source_sha = str(executable.get("source_sha256") or "")
    as_of = str(executable.get("as_of") or "")
    if (
        not fingerprint.startswith("sha256:")
        or len(fingerprint) != 71
        or any(character not in "0123456789abcdef" for character in fingerprint[7:])
    ):
        return "manifest executable_universe fingerprint is invalid"
    if (
        not source_sha.startswith("sha256:")
        or len(source_sha) != 71
        or any(character not in "0123456789abcdef" for character in source_sha[7:])
    ):
        return "manifest executable_universe source hash is invalid"
    if not as_of:
        return "manifest executable_universe as_of is missing"

    ready_path = (
        Path(project_root)
        / "reports"
        / "top50_data_readiness"
        / "latest_ready.json"
    )
    if not ready_path.is_file():
        return "current READY pointer is missing"
    try:
        ready_payload = json.loads(ready_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"current READY pointer is unreadable: {exc}"
    if not isinstance(ready_payload, dict) or ready_payload.get("ready") is not True:
        return "current READY pointer is not a READY payload"
    if str(ready_payload.get("as_of") or "") != as_of:
        return "current READY pointer as_of does not match manifest"
    if str(ready_payload.get("fingerprint") or "") != fingerprint:
        return "current READY pointer fingerprint does not match manifest"
    if _sha256(ready_path) != source_sha.removeprefix("sha256:"):
        return "current READY pointer bytes do not match manifest source_sha256"
    return None


def execution_required_mark_time(
    manifest: Mapping[str, object],
    *,
    execution_utc: str | None = None,
) -> pd.Timestamp:
    """Return the mark bar required for the manifest's next execution."""

    raw_signal_end = str(manifest.get("signal_end_date") or "").strip()
    if not raw_signal_end:
        raise ValueError("manifest signal_end_date is missing")
    signal_end = pd.Timestamp(raw_signal_end)
    if signal_end.tzinfo is None:
        signal_end = signal_end.tz_localize("UTC")
    else:
        signal_end = signal_end.tz_convert("UTC")
    raw_clock = str(execution_utc or manifest.get("execution_utc") or "01:05")
    try:
        hour_text, minute_text = raw_clock.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"manifest execution_utc is invalid: {raw_clock!r}") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"manifest execution_utc is invalid: {raw_clock!r}")
    execution_target = signal_end.normalize() + pd.Timedelta(
        days=1,
        hours=hour,
        minutes=minute,
    )
    return execution_target - pd.Timedelta(hours=1, minutes=5)


def write_prepare_receipt(
    *,
    project_root: Path,
    manifest_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    project_root = Path(project_root).resolve()
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    missing_manifest = [
        key
        for key in RECEIPT_MANIFEST_FIELDS
        if manifest.get(key) in (None, "")
    ]
    if missing_manifest:
        raise ValueError(
            "manifest is missing required receipt fields: "
            + ", ".join(missing_manifest)
        )
    audit_paths = [Path(project_root) / name for name in AUDIT_FILE_NAMES]
    missing_audits = [str(path) for path in audit_paths if not path.is_file()]
    if missing_audits:
        raise FileNotFoundError(
            "cannot write prepare receipt; missing audit file(s): "
            + ", ".join(missing_audits)
        )
    readiness_issue = _readiness_commitment_issue(
        manifest, project_root=project_root
    )
    if readiness_issue is not None:
        raise ValueError(
            "cannot write prepare receipt: " + readiness_issue
        )
    receipt = {
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "track": RECEIPT_TRACK,
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
            name: _sha256(Path(project_root) / name) for name in AUDIT_FILE_NAMES
        },
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(receipt_path)
    return receipt


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    """Write a JSON artifact without exposing a half-written manifest."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _audit_last_mark(audit: Mapping[str, object]) -> pd.Timestamp:
    summary = audit.get("summary")
    raw = summary.get("last_mark") if isinstance(summary, Mapping) else None
    if raw in (None, ""):
        raise ValueError("data audit did not report a last_mark")
    stamp = pd.Timestamp(str(raw))
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _update_manifest_after_mark_audit(
    manifest_path: Path,
    manifest: Mapping[str, object],
    audit: Mapping[str, object],
) -> dict[str, object]:
    """Refresh only fields whose proof changes when the mark tail advances."""

    updated = dict(manifest)
    last_mark = _audit_last_mark(audit)
    provenance = audit.get("provenance")
    fingerprint = (
        str(provenance.get("fingerprint") or "")
        if isinstance(provenance, Mapping)
        else ""
    )
    if not fingerprint.startswith("sha256:"):
        raise ValueError("data audit did not report a data fingerprint")
    updated["last_mark"] = last_mark.isoformat()
    updated["data_fingerprint"] = fingerprint
    updated["data_audit_passed"] = bool(audit.get("passed"))
    updated["data_audit_hard_failures"] = list(
        audit.get("hard_failures") or []
    )[:20]
    updated["data_audit_warnings"] = list(audit.get("warnings") or [])[:20]
    _write_json_atomic(manifest_path, updated)
    return updated


def _run_checked(command: Sequence[str], *, project_root: Path) -> int:
    print("running: " + " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=project_root, check=False)
    return int(completed.returncode)


def _finalize_execution(
    args: argparse.Namespace,
    *,
    project_root: Path,
    lock_path: Path,
    now: datetime | None = None,
) -> int:
    """Append the post-midnight mark tail without rebuilding the signal.

    The normal prepare run completes before the 00:00 UTC hourly bar is
    published.  This bounded finalization starts after that bar is due, fetches
    only mark tails, refreshes the data audit, and republishes the receipt so
    the 01:05 executor can reuse it directly.
    """

    manifest_path = project_root / "reports" / "ls45_live_g175" / "manifest.json"
    targets_path = project_root / "reports" / "ls45_live_g175" / "oos_targets.csv"
    receipt_path = Path(args.receipt_out).expanduser()
    data_audit_path = project_root / "reports" / "ls45_live_g175" / "data_audit.json"
    data_audit_markdown = project_root / "reports" / "ls45_live_g175" / "data_audit.md"
    signal_audit_path = (
        project_root / "reports" / "ls45_live_g175_live" / "signal_equivalence.json"
    )
    if not manifest_path.is_file() or not targets_path.is_file():
        print(
            "execution finalize refused: prepare manifest or targets file is missing",
            file=sys.stderr,
        )
        return 3

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        deadline = time.monotonic() + float(args.execution_lock_wait_seconds)
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    print(f"execution finalize skipped: lock is busy: {lock_path}")
                    return 0
                time.sleep(1.0)
        try:
            valid, reason = check_prepare_receipt(
                receipt_path=receipt_path,
                manifest_path=manifest_path,
                max_age_minutes=float(args.max_age_minutes),
                project_root=project_root,
                now=now,
                require_current_mark=False,
            )
            if not valid:
                print(f"execution finalize refused: {reason}", file=sys.stderr)
                return 3
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest is not a JSON object")
            required_mark = execution_required_mark_time(manifest)
            raw_dir = Path(str(manifest.get("raw_dir") or "data/raw/bitget_derivatives/merged_oos_20261112"))
            if not raw_dir.is_absolute():
                raw_dir = project_root / raw_dir
            download_command = [
                sys.executable,
                str(project_root / "scripts" / "download_bitget_derivatives_data.py"),
                "--output-dir",
                str(raw_dir),
                "--types",
                "mark",
                "--skip-funding",
                "--mark-tail-only",
                "--required-mark-time",
                required_mark.isoformat(),
                "--wait-for-live-mark-seconds",
                str(float(args.mark_wait_seconds)),
                "--wait-for-live-mark-poll-seconds",
                str(float(args.mark_poll_seconds)),
                "--execution-utc",
                str(manifest.get("execution_utc") or "01:05"),
            ]
            status = _run_checked(download_command, project_root=project_root)
            if status != 0:
                return status
            expected_targets_hash = str(manifest.get("targets_sha256") or "")
            if not expected_targets_hash or _sha256(targets_path) != expected_targets_hash:
                print(
                    "execution finalize refused: target ledger changed during mark refresh",
                    file=sys.stderr,
                )
                return 1
            data_audit_command = [
                sys.executable,
                str(project_root / "scripts" / "audit_derivatives_data.py"),
                "--raw-dir",
                str(raw_dir),
                "--manifest",
                str(manifest_path),
                "--targets-file",
                str(targets_path),
                "--json-out",
                str(data_audit_path),
                "--markdown-out",
                str(data_audit_markdown),
                "--required-leverage",
                "4.0",
                "--require-all-funding-fresh",
            ]
            status = _run_checked(data_audit_command, project_root=project_root)
            if status != 0:
                return status
            audit = json.loads(data_audit_path.read_text(encoding="utf-8"))
            if not isinstance(audit, dict) or audit.get("passed") is not True:
                print("execution finalize refused: refreshed data audit did not pass", file=sys.stderr)
                return 1
            if _audit_last_mark(audit) < required_mark:
                print(
                    f"execution finalize refused: refreshed mark is before {required_mark}",
                    file=sys.stderr,
                )
                return 1
            updated_manifest = _update_manifest_after_mark_audit(
                manifest_path,
                manifest,
                audit,
            )
            # Re-run the audit so its manifest hash points at the updated
            # manifest.  The data fingerprint must remain unchanged.
            status = _run_checked(data_audit_command, project_root=project_root)
            if status != 0:
                return status
            audit_after_manifest = json.loads(data_audit_path.read_text(encoding="utf-8"))
            expected_fingerprint = str(updated_manifest.get("data_fingerprint") or "")
            actual_fingerprint = str(
                (audit_after_manifest.get("provenance") or {}).get("fingerprint")
                if isinstance(audit_after_manifest, dict)
                else ""
            )
            if actual_fingerprint != expected_fingerprint:
                print(
                    "execution finalize refused: data fingerprint changed while updating manifest",
                    file=sys.stderr,
                )
                return 1
            signal_command = [
                sys.executable,
                str(project_root / "scripts" / "audit_signal_equivalence.py"),
                "--targets-file",
                str(targets_path),
                "--manifest-file",
                str(manifest_path),
                "--json-out",
                str(signal_audit_path),
                "--track",
                "ls104-g175-m090",
            ]
            status = _run_checked(signal_command, project_root=project_root)
            if status != 0:
                return status
            signal_receipt = project_root / "reports" / "ls45_live_g175" / "signal_receipt.csv"
            if signal_receipt.is_file():
                signal_frame = pd.read_csv(signal_receipt)
                if "last_mark" in signal_frame.columns:
                    signal_frame["last_mark"] = str(_audit_last_mark(audit_after_manifest))
                    temporary = signal_receipt.with_suffix(signal_receipt.suffix + ".tmp")
                    signal_frame.to_csv(temporary, index=False)
                    temporary.replace(signal_receipt)
            write_prepare_receipt(
                project_root=project_root,
                manifest_path=manifest_path,
                receipt_path=receipt_path,
            )
            print(
                "execution finalize complete: mark tail "
                f"{_audit_last_mark(audit_after_manifest).isoformat()}"
            )
            return 0
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def build_refresh_commands(
    *,
    make_command: str = "/usr/bin/make",
    project_root: Path = PROJECT_ROOT,
    include_top50_readiness: bool = False,
) -> list[list[str]]:
    """Return the exact LS104 refresh/audit sequence.

    ``derivatives-ls104-signal`` rebuilds the manifest as well as the target
    CSV, so refreshing marks or funding can never leave the executor with an
    old fingerprint under a new raw tree.  The sequence deliberately contains
    no execution or notification target.
    """

    commands = [
        [make_command, "derivatives-live-data"],
    ]
    if include_top50_readiness:
        commands.append([make_command, "top50-readiness-unlocked"])
    commands.append([make_command, "top50-readiness-check"])
    commands.extend(
        [
            [make_command, "derivatives-ls104-signal"],
            [make_command, "audit-data-chain"],
            [make_command, "audit-data-ls104"],
            [make_command, "audit-symbols-ls104"],
            [make_command, "audit-contract-specs-ls104"],
            [make_command, "audit-signal-ls104"],
        ]
    )
    return commands


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
        "--finalize-execution",
        action="store_true",
        help="fetch the post-midnight mark tail and republish the execution receipt",
    )
    parser.add_argument(
        "--mark-wait-seconds",
        type=float,
        default=120.0,
        help="bounded wait for the required post-midnight mark bar",
    )
    parser.add_argument(
        "--mark-poll-seconds",
        type=float,
        default=15.0,
        help="poll interval for the post-midnight mark tail",
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
    now: datetime | None = None,
    require_current_mark: bool = True,
) -> tuple[bool, str]:
    """Return whether a prepare receipt proves the book at ``now``.

    Receipt freshness is time-sensitive at the 01:05 execution boundary: a
    receipt built at 00:55 can only contain the 23:00 completed mark bar, while
    the executor's data audit requires the 00:00 bar after 01:05.  The receipt
    must therefore be rejected even when it is otherwise fresh; the caller must
    run the bounded data refresh rather than reuse a pre-boundary snapshot.
    """

    if not math.isfinite(float(max_age_minutes)) or max_age_minutes < 0.0:
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
    if receipt.get("track") != RECEIPT_TRACK:
        return False, "prepare receipt track does not match"
    expected_manifest_path = (
        Path(project_root) / "reports" / "ls45_live_g175" / "manifest.json"
    ).resolve()
    try:
        receipt_manifest_path = Path(str(receipt.get("manifest_path") or "")).resolve()
    except (OSError, RuntimeError):
        return False, "prepare receipt manifest path is invalid"
    if receipt_manifest_path != expected_manifest_path:
        return False, "prepare receipt manifest path does not match"
    try:
        prepared_at = datetime.fromisoformat(
            str(receipt.get("prepared_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        return False, "prepare receipt has no valid prepared_at"
    if prepared_at.tzinfo is None:
        prepared_at = prepared_at.replace(tzinfo=timezone.utc)
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)
    age_minutes = (moment - prepared_at.astimezone(timezone.utc)).total_seconds() / 60.0
    if age_minutes < -1.0:
        return False, f"prepare receipt is in the future ({age_minutes:.1f}m)"
    if age_minutes > float(max_age_minutes):
        return False, (
            f"prepare receipt is stale ({age_minutes:.1f}m > "
            f"{float(max_age_minutes):g}m)"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"manifest unreadable: {exc}"
    if not isinstance(manifest, dict):
        return False, "manifest is not a JSON object"
    readiness_issue = _readiness_commitment_issue(
        manifest, project_root=Path(project_root)
    )
    if readiness_issue is not None:
        return False, readiness_issue
    missing_manifest = [
        key
        for key in RECEIPT_MANIFEST_FIELDS
        if manifest.get(key) in (None, "")
    ]
    if missing_manifest:
        return False, (
            "manifest is missing required receipt fields: "
            + ", ".join(missing_manifest)
        )
    for key in RECEIPT_MANIFEST_FIELDS:
        if receipt.get(key) != manifest.get(key):
            return False, f"prepare receipt {key} does not match manifest"
    if require_current_mark:
        try:
            last_mark = pd.Timestamp(str(manifest.get("last_mark") or ""))
        except (TypeError, ValueError):
            return False, "prepare receipt has an invalid last_mark"
        if pd.isna(last_mark):
            return False, "prepare receipt has an invalid last_mark"
        last_mark = (
            last_mark.tz_localize("UTC")
            if last_mark.tzinfo is None
            else last_mark.tz_convert("UTC")
        )
        required_mark = required_last_mark_time(moment)
        if last_mark < required_mark:
            return False, (
                f"prepare receipt last_mark {last_mark.isoformat()} is before "
                f"the current execution requirement {required_mark.isoformat()}"
            )
    if receipt.get("manifest_sha256") != _sha256(manifest_path):
        return False, "prepare receipt manifest hash does not match"
    raw_audit_files = receipt.get("audit_files")
    if not isinstance(raw_audit_files, dict):
        return False, "prepare receipt audit_files must be an object"
    expected_audits = set(AUDIT_FILE_NAMES)
    observed_audits = set(raw_audit_files)
    if observed_audits != expected_audits:
        missing = sorted(expected_audits.difference(observed_audits))
        extra = sorted(observed_audits.difference(expected_audits))
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("unexpected=" + ",".join(extra))
        return False, "prepare receipt audit_files are incomplete: " + "; ".join(details)
    for name in AUDIT_FILE_NAMES:
        digest = raw_audit_files[name]
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
        # The CMC panel advances once per day.  Intraday refreshes must update
        # venue marks/funding and rebuild LS104 without repeatedly rebuilding
        # the same Top50 ranking and notification evidence.
        include_top50_readiness=bool(args.pre_execution),
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

    if args.finalize_execution:
        if args.dry_run:
            print(
                "finalize: refresh mark tail, data audit, signal audit, receipt"
            )
            return 0
        return _finalize_execution(
            args,
            project_root=project_root,
            lock_path=lock_path,
        )

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
