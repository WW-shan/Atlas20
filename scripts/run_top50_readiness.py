"""Build and audit the executable Top50 data handoff.

This command only reads the processed CMC panel and the existing Bitget raw
trees.  When a selected mapped member already has a file-level gap, it invokes
the same downloader and mark-gap repair tools used by the live chain once, then
re-runs the evidence audit.  It never places orders and never changes the live
LS104 target, state or journal.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.live_chain import (  # noqa: E402
    last_completed_utc_day,
    panel_lags_last_completed_day,
)
from atlas20.derivatives.top50_readiness import (  # noqa: E402
    Top50Selection,
    _payload_fingerprint,
    assess_selection,
    build_notification_events,
    format_event_message,
    load_state,
    publish_readiness_payload,
    queue_notification_events,
    rank_current_candidates,
    reconcile_notification_queue,
    record_notification_result,
    select_executable_top50,
    validate_ready_payload,
    write_state,
)

DEFAULT_CONFIG = PROJECT_ROOT / "config" / "base.yaml"
DEFAULT_PANEL = PROJECT_ROOT / "data" / "processed" / "panel_daily.csv"
DEFAULT_METADATA = PROJECT_ROOT / "data" / "processed" / "metadata.csv"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "bitget_derivatives" / "merged_oos_20261112"
DEFAULT_WARMUP_DIR = PROJECT_ROOT / "data" / "raw" / "bitget_derivatives" / "merged_20261009"
DEFAULT_WARMUP_MARKET_DIR = (
    PROJECT_ROOT / "data" / "raw" / "bitget_derivatives" / "merged_market_20261009"
)
DEFAULT_STATE = PROJECT_ROOT / "data" / "top50_readiness_state.json"
DEFAULT_REPORTS = PROJECT_ROOT / "reports" / "top50_data_readiness"
DEFAULT_LOCK = PROJECT_ROOT / "data" / "derivatives_execution.lock"
DEFAULT_OOS_START = pd.Timestamp("2026-09-01", tz="UTC")
DEFAULT_WARMUP_START = pd.Timestamp("2022-01-01", tz="UTC")
DEFAULT_WARMUP_END = pd.Timestamp("2026-09-21", tz="UTC")


@dataclass(frozen=True)
class ReadinessSession:
    project_root: Path
    config_path: Path
    panel_path: Path
    metadata_path: Path
    raw_dir: Path
    warmup_mark_dir: Path
    warmup_market_dir: Path
    symbol_map_path: Path
    state_path: Path
    reports_dir: Path
    lock_path: Path
    oos_start: pd.Timestamp
    warmup_start: pd.Timestamp
    warmup_end: pd.Timestamp
    universe_limit: int = 60


class PublishedReadinessError(RuntimeError):
    """A cycle failure whose blocked evidence and alert were already persisted."""


def _as_utc(value: str | datetime | pd.Timestamp) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def check_current_ready(
    *,
    reports_dir: Path,
    now: pd.Timestamp,
) -> tuple[bool, str]:
    expected = last_completed_utc_day(_as_utc(now).to_pydatetime())
    path = Path(reports_dir) / "latest_ready.json"
    if not path.is_file():
        return False, f"current ready pointer is missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"current ready pointer is unreadable: {exc}"
    if not isinstance(payload, dict):
        return False, "current ready pointer must be a JSON object"
    if payload.get("ready") is not True:
        return False, "current ready pointer is not READY"
    if str(payload.get("as_of") or "") != expected.isoformat():
        return False, (
            "current ready pointer is stale: "
            f"as_of={payload.get('as_of')!r}, require {expected.isoformat()}"
        )
    try:
        validate_ready_payload(payload)
    except ValueError as exc:
        return False, f"current ready pointer is invalid: {exc}"
    fingerprint = str(payload.get("fingerprint") or "")
    if not fingerprint or fingerprint != _payload_fingerprint(payload):
        return False, "current ready pointer fingerprint does not match its bytes"
    latest_path = Path(reports_dir) / "latest.json"
    if not latest_path.is_file():
        return False, f"current readiness report is missing: {latest_path}"
    try:
        latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"current readiness report is unreadable: {exc}"
    if latest_payload != payload:
        return False, "current ready pointer does not match latest readiness report"
    return True, f"current Top50 readiness is READY as_of={expected.isoformat()}"


def build_backfill_commands(
    *,
    session: ReadinessSession,
    selection: Top50Selection,
    warmup_members: set[str],
    live_members: set[str],
    python: str,
    oos_start: pd.Timestamp,
    warmup_end: pd.Timestamp,
    end: pd.Timestamp,
) -> list[list[str]]:
    """Return existing-tool commands only for the evidence layers that failed."""

    selected_ids = {member.coin_id for member in selection.members}
    unknown = (set(warmup_members) | set(live_members)).difference(selected_ids)
    if unknown:
        raise ValueError(
            "backfill members are not selected mapped members: "
            + ", ".join(sorted(unknown))
        )
    downloader = [
        python,
        str(Path("scripts") / "download_bitget_derivatives_data.py"),
        "--panel",
        str(session.panel_path),
    ]
    warmup_end_date = _as_utc(warmup_end).date().isoformat()
    live_end_date = (_as_utc(end) + pd.Timedelta(days=1)).date().isoformat()
    commands: list[list[str]] = []
    if warmup_members:
        symbols = ",".join(sorted(warmup_members))
        commands.extend(
            [
                [
                    *downloader,
                    "--output-dir",
                    str(session.warmup_mark_dir),
                    "--start",
                    _as_utc(session.warmup_start).date().isoformat(),
                    "--end",
                    warmup_end_date,
                    "--types",
                    "mark",
                    "--skip-funding",
                    "--symbols",
                    symbols,
                ],
                [
                    *downloader,
                    "--output-dir",
                    str(session.warmup_market_dir),
                    "--start",
                    _as_utc(session.warmup_start).date().isoformat(),
                    "--end",
                    warmup_end_date,
                    "--types",
                    "market",
                    "--skip-funding",
                    "--symbols",
                    symbols,
                ],
                [
                    python,
                    str(Path("scripts") / "repair_bitget_mark_gaps.py"),
                    "--raw-dir",
                    str(session.warmup_mark_dir),
                    "--start",
                    _as_utc(session.warmup_start).date().isoformat(),
                    "--end",
                    warmup_end_date,
                    "--symbols",
                    symbols,
                ],
            ]
        )
    if live_members:
        symbols = ",".join(sorted(live_members))
        commands.extend(
            [
                [
                    *downloader,
                    "--output-dir",
                    str(session.raw_dir),
                    "--start",
                    _as_utc(oos_start).date().isoformat(),
                    "--end",
                    live_end_date,
                    "--types",
                    "mark,market",
                    "--symbols",
                    symbols,
                ],
                [
                    python,
                    str(Path("scripts") / "repair_bitget_mark_gaps.py"),
                    "--raw-dir",
                    str(session.raw_dir),
                    "--start",
                    _as_utc(oos_start).date().isoformat(),
                    "--end",
                    live_end_date,
                    "--symbols",
                    symbols,
                ],
            ]
        )
    return commands


def _backfill_scopes(
    payload: dict[str, object],
    blocked: set[str],
) -> tuple[set[str], set[str]]:
    warmup: set[str] = set()
    live: set[str] = set()
    members = payload.get("members")
    if not isinstance(members, list):
        return warmup, live
    for item in members:
        if not isinstance(item, dict):
            continue
        coin_id = str(item.get("coin_id") or "")
        if coin_id not in blocked:
            continue
        details = item.get("failure_details")
        rendered = (
            [str(value) for value in details] if isinstance(details, list) else []
        )
        section_failures: list[str] = []
        for section in (
            "warmup_mark",
            "warmup_market",
            "warmup_market_alignment",
            "live_mark",
            "live_market",
            "live_market_alignment",
            "funding",
        ):
            evidence = item.get(section)
            if not isinstance(evidence, dict):
                continue
            failures = evidence.get("failures")
            if isinstance(failures, list) and failures:
                section_failures.append(section)
        warmup_sections = {
            "warmup_mark",
            "warmup_market",
            "warmup_market_alignment",
        }
        live_sections = {
            "live_mark",
            "live_market",
            "live_market_alignment",
            "funding",
        }
        warmup_failed = any(
            value.startswith(("warmup_mark:", "warmup_market:"))
            for value in rendered
        )
        live_failed = any(
            value.startswith(("live_mark:", "live_market:", "funding:"))
            for value in rendered
        )
        # The full data audit can expose a funding publication/settlement issue
        # that the lightweight funding-coverage probe does not classify.  A
        # member-specific funding audit failure is still repairable with the
        # existing live downloader.
        funding_audit_prefix = f"audit: funding.{coin_id}."
        if any(value.startswith(funding_audit_prefix) for value in rendered):
            live_failed = True
        if warmup_failed or warmup_sections.intersection(section_failures):
            warmup.add(coin_id)
        if live_failed or live_sections.intersection(section_failures):
            live.add(coin_id)
    return warmup, live


def _run_subprocess(command: list[str], *, cwd: Path) -> int:
    return subprocess.run(command, cwd=cwd, check=False).returncode


def _assessment_kwargs(
    session: ReadinessSession,
    *,
    selection: Top50Selection,
    now: pd.Timestamp,
) -> dict[str, Any]:
    return {
        "selection": selection,
        "panel_path": session.panel_path,
        "symbol_map_path": session.symbol_map_path,
        "raw_dir": session.raw_dir,
        "warmup_mark_dir": session.warmup_mark_dir,
        "warmup_market_dir": session.warmup_market_dir,
        "reports_dir": session.reports_dir,
        "warmup_start": session.warmup_start,
        "warmup_end": session.warmup_end,
        "oos_start": session.oos_start,
        "latest_signal_day": selection.as_of,
        "now": now,
    }


def _deliver_pending_notifications(
    *,
    state: dict[str, object],
    moment: pd.Timestamp,
    send_message: Callable[[str], None],
) -> list[str]:
    notifications = state.get("notifications")
    if not isinstance(notifications, dict):
        raise ValueError("state notifications must be an object")
    pending_value = notifications.get("pending")
    if not isinstance(pending_value, dict):
        raise ValueError("state notifications pending must be an object")
    pending = dict(pending_value)
    failures: list[str] = []
    event_priority = {
        "TOP50_ENTER": 0,
        "TOP50_DATA_READY": 1,
        "TOP50_DATA_BLOCKED": 1,
        "TOP20_ENTER": 2,
    }

    def delivery_key(key: str) -> tuple[int, str]:
        event = pending.get(key)
        event_type = str(event.get("event") or "") if isinstance(event, dict) else ""
        return (event_priority.get(event_type, 99), str(key))

    for key in sorted(pending, key=delivery_key):
        event = pending[key]
        if not isinstance(event, dict):
            failures.append(str(key))
            continue
        try:
            send_message(format_event_message(event))
        except Exception as exc:  # noqa: BLE001 - persisted for retry
            failures.append(str(key))
            record_notification_result(
                state,
                event,
                sent=False,
                error=str(exc),
                sent_at=moment.isoformat(),
            )
        else:
            record_notification_result(
                state,
                event,
                sent=True,
                error=None,
                sent_at=moment.isoformat(),
            )
    return failures


def _mark_members_blocked(
    payload: dict[str, object],
    *,
    coin_ids: set[str],
    detail: str,
) -> None:
    member_rows = payload.get("members")
    if isinstance(member_rows, list):
        for member in member_rows:
            if not isinstance(member, dict):
                continue
            if str(member.get("coin_id") or "") not in coin_ids:
                continue
            details = member.get("failure_details")
            rendered = list(details) if isinstance(details, list) else []
            rendered.append(detail)
            member["failure_details"] = rendered
            member["status"] = "BLOCKED"
    payload["ready"] = False


def run_readiness_cycle(
    *,
    session: ReadinessSession,
    now: pd.Timestamp,
    notify: bool,
    dry_run: bool,
    backfill: bool = True,
    runner: Callable[[list[str]], int],
    send_message: Callable[[str], None],
    rank_fn: Callable[..., pd.DataFrame] = rank_current_candidates,
    assess_fn: Callable[..., tuple[dict[str, object], set[str]]] = assess_selection,
    now_fn: Callable[[], pd.Timestamp] = _utc_now,
) -> dict[str, object]:
    """Run one daily selection, optional bounded backfill and publication."""

    moment = _as_utc(now)
    latest_signal_day = last_completed_utc_day(moment.to_pydatetime())
    ranked = rank_fn(
        config_path=session.config_path,
        panel_path=session.panel_path,
        metadata_path=session.metadata_path,
        as_of=latest_signal_day,
        limit=session.universe_limit,
    )
    mapping = pd.read_csv(session.symbol_map_path)
    selection = select_executable_top50(
        ranked,
        mapping,
        as_of=latest_signal_day,
    )
    previous = load_state(session.state_path)
    initialized = bool(previous.get("initialized"))
    last_as_of = str(previous.get("last_as_of") or "")
    if not dry_run and initialized and last_as_of:
        try:
            previous_day = datetime.fromisoformat(last_as_of).date()
        except ValueError as exc:
            raise ValueError(f"top50 state has an invalid last_as_of: {last_as_of}") from exc
        if selection.as_of < previous_day:
            raise ValueError(
                "refusing to publish older as_of "
                f"{selection.as_of.isoformat()} than state {last_as_of}"
            )
    payload, blocked = assess_fn(
        **_assessment_kwargs(session, selection=selection, now=moment)
    )
    commands: list[list[str]] = []
    backfill_error: str | None = None
    if backfill and blocked and not dry_run:
        warmup_members, live_members = _backfill_scopes(payload, blocked)
        commands = build_backfill_commands(
            session=session,
            selection=selection,
            warmup_members=warmup_members,
            live_members=live_members,
            python=sys.executable,
            oos_start=session.oos_start,
            warmup_end=session.warmup_end,
            end=moment,
        )
        for command in commands:
            failure: str | None
            try:
                completed = runner(command)
            except Exception as exc:  # noqa: BLE001 - persisted for fail-closed alert
                failure = (
                    "top50 backfill command raised "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                failure = (
                    f"top50 backfill command failed ({completed}): {' '.join(command)}"
                    if completed != 0
                    else None
                )
            if failure is not None:
                backfill_error = failure
                affected = warmup_members | live_members
                _mark_members_blocked(
                    payload,
                    coin_ids=affected,
                    detail=f"backfill: {backfill_error}",
                )
                blocked.update(affected)
                break
        if commands and backfill_error is None:
            affected = warmup_members | live_members
            try:
                reassessed_at = _as_utc(now_fn())
                if reassessed_at < moment:
                    raise ValueError("readiness clock moved backwards after backfill")
                payload, blocked = assess_fn(
                    **_assessment_kwargs(
                        session,
                        selection=selection,
                        now=reassessed_at,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - persisted fail-closed
                backfill_error = (
                    f"top50 reassessment raised {type(exc).__name__}: {exc}"
                )
                _mark_members_blocked(
                    payload,
                    coin_ids=affected,
                    detail=backfill_error,
                )
                blocked.update(affected)

    initialized_now = not initialized
    events = build_notification_events(previous, payload, initialized=initialized)

    paths: dict[str, Path] = {}
    if not dry_run:
        publish_payload = {
            key: value for key, value in payload.items() if key != "audit_detail"
        }
        audit_payload = payload.get("audit_detail")
        if not isinstance(audit_payload, dict):
            audit_payload = {
                "passed": bool(payload.get("ready")),
                "hard_failures": [],
                "warnings": [],
                "checks": [],
            }
        paths = publish_readiness_payload(
            reports_dir=session.reports_dir,
            payload=publish_payload,
            audit_payload=audit_payload,
        )

        state = previous
        state["version"] = 1
        state["initialized"] = True
        state["last_as_of"] = payload.get("as_of")
        member_rows = payload.get("members")
        top20_rows = payload.get("top20")
        if not isinstance(member_rows, list) or not isinstance(top20_rows, list):
            raise ValueError("readiness payload must contain member lists")
        if not all(isinstance(item, dict) for item in (*member_rows, *top20_rows)):
            raise ValueError("readiness member lists must contain objects")
        state["members"] = [str(item["coin_id"]) for item in member_rows]
        state["top20"] = [str(item["coin_id"]) for item in top20_rows]
        state["member_status"] = {
            str(item["coin_id"]): str(item["status"])
            for item in member_rows
        }
        reconcile_notification_queue(state, payload)
        queue_notification_events(state, events)
        notification_failures: list[str] = []
        if notify:
            notification_failures = _deliver_pending_notifications(
                state=state,
                moment=moment,
                send_message=send_message,
            )
        write_state(session.state_path, state)
        failures: list[str] = []
        if backfill_error is not None:
            failures.append(backfill_error)
        if notification_failures:
            failures.append(
                "Telegram delivery failed for: " + ", ".join(notification_failures)
            )
        if failures:
            raise PublishedReadinessError("; ".join(failures))

    return {
        "payload": payload,
        "blocked": sorted(blocked),
        "events": events,
        "initialized_now": initialized_now,
        "backfill_commands": commands,
        "paths": paths,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--warmup-mark-dir", type=Path, default=DEFAULT_WARMUP_DIR)
    parser.add_argument(
        "--warmup-market-dir", type=Path, default=DEFAULT_WARMUP_MARKET_DIR
    )
    parser.add_argument("--symbol-map", type=Path, default=None)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--oos-start", default=DEFAULT_OOS_START.date().isoformat())
    parser.add_argument(
        "--warmup-start", default=DEFAULT_WARMUP_START.date().isoformat()
    )
    parser.add_argument("--warmup-end", default=DEFAULT_WARMUP_END.date().isoformat())
    parser.add_argument("--universe-limit", type=int, default=60)
    parser.add_argument("--now", default=None)
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--notify-only", action="store_true")
    parser.add_argument("--check-current", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backfill", action="store_true")
    parser.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--wait-seconds", type=float, default=900.0)
    parser.add_argument("--no-lock", action="store_true")
    args = parser.parse_args(argv)
    if args.wait_seconds < 0.0:
        parser.error("--wait-seconds must be non-negative")

    moment = (
        _as_utc(datetime.fromisoformat(args.now.replace("Z", "+00:00")))
        if args.now
        else pd.Timestamp.now(tz="UTC")
    )
    if args.check_current:
        ok, reason = check_current_ready(reports_dir=args.reports_dir, now=moment)
        print(reason)
        return 0 if ok else 1
    lock_file = None
    if not args.no_lock:
        from filelock import FileLock, Timeout

        lock = FileLock(str(args.lock_file))
        try:
            lock.acquire(timeout=float(args.wait_seconds))
        except Timeout:
            print(
                f"another execution/refresh holds {args.lock_file}; skipping",
                file=sys.stderr,
            )
            # A skippable market rebuild is not the same as a delivered
            # notification.  The fallback wrapper must expose an undelivered
            # pending queue so it can continue data recovery and report a
            # non-zero notification outcome.
            return 1 if (args.notify_only or args.notify) else 0
        lock_file = lock
    try:
        if args.notify_only:
            state = load_state(args.state_file)
            failures = _deliver_pending_notifications(
                state=state,
                moment=moment,
                send_message=lambda message: _send_telegram(message, moment=moment),
            )
            write_state(args.state_file, state)
            if failures:
                print(
                    "top50 Telegram delivery failed for: " + ", ".join(failures),
                    file=sys.stderr,
                )
                return 1
            return 0
        if panel_lags_last_completed_day(args.panel, moment.to_pydatetime()):
            message = (
                "panel does not carry the last completed UTC day for "
                f"{moment.isoformat()}: {args.panel}"
            )
            if args.notify:
                _send_telegram(
                    "Atlas20 Top50 readiness ERROR\n" + message,
                    moment=moment,
                )
            raise SystemExit(message)
        session = ReadinessSession(
            project_root=PROJECT_ROOT,
            config_path=args.config,
            panel_path=args.panel,
            metadata_path=args.metadata,
            raw_dir=args.raw_dir,
            warmup_mark_dir=args.warmup_mark_dir,
            warmup_market_dir=args.warmup_market_dir,
            symbol_map_path=args.symbol_map or args.raw_dir / "symbol_map.csv",
            state_path=args.state_file,
            reports_dir=args.reports_dir,
            lock_path=args.lock_file,
            oos_start=_as_utc(args.oos_start),
            warmup_start=_as_utc(args.warmup_start),
            warmup_end=_as_utc(args.warmup_end),
            universe_limit=int(args.universe_limit),
        )
        try:
            result = run_readiness_cycle(
                session=session,
                now=moment,
                notify=bool(args.notify),
                dry_run=bool(args.dry_run),
                backfill=not bool(args.no_backfill),
                runner=lambda command: _run_subprocess(
                    command,
                    cwd=session.project_root,
                ),
                send_message=lambda message: _send_telegram(
                    message,
                    moment=moment,
                ),
            )
        except PublishedReadinessError:
            raise
        except Exception as exc:
            if args.notify:
                _send_telegram(
                    "Atlas20 Top50 readiness ERROR\n"
                    f"{type(exc).__name__}: {exc}",
                    moment=moment,
                )
            raise
    finally:
        if lock_file is not None:
            lock_file.release()

    payload = result.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("top50 readiness returned no payload object")
    blocked = result.get("blocked")
    blocked_count = len(blocked) if isinstance(blocked, list) else 0
    print(
        "top50 readiness: "
        f"{'READY' if payload.get('ready') else 'BLOCKED'} "
        f"as_of={payload.get('as_of')} "
        f"blocked={blocked_count}"
    )
    return 0 if bool(payload.get("ready")) else 1


def _send_telegram(message: str, *, moment: pd.Timestamp) -> None:
    import os

    from scripts.send_telegram_signal import _chat_ids, send_telegram_message

    chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
    if not chat_ids:
        raise RuntimeError("ATLAS20_TELEGRAM_CHAT_ID is not set")
    token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("ATLAS20_TELEGRAM_BOT_TOKEN is not set")
    api_base = os.environ.get("ATLAS20_TELEGRAM_API_BASE", "https://api.telegram.org")
    for chat_id in chat_ids:
        send_telegram_message(
            message,
            token=token,
            chat_id=chat_id,
            api_base=api_base,
        )


if __name__ == "__main__":
    raise SystemExit(main())
