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
    assess_selection,
    build_notification_events,
    format_event_message,
    load_state,
    publish_readiness_payload,
    queue_notification_events,
    rank_current_candidates,
    record_notification_result,
    select_executable_top50,
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


def _as_utc(value: str | datetime | pd.Timestamp) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def build_backfill_commands(
    *,
    session: ReadinessSession,
    selection: Top50Selection,
    blocked_members: set[str],
    python: str,
    oos_start: pd.Timestamp,
    warmup_end: pd.Timestamp,
    end: pd.Timestamp,
) -> list[list[str]]:
    """Return the exact existing-tool commands for mapped blocked members."""

    selected_ids = {member.coin_id for member in selection.members}
    unknown = set(blocked_members).difference(selected_ids)
    if unknown:
        raise ValueError(
            "blocked_members are not selected mapped members: "
            + ", ".join(sorted(unknown))
        )
    blocked = sorted(blocked_members)
    if not blocked:
        return []
    symbols = ",".join(blocked)
    downloader = [
        python,
        str(Path("scripts") / "download_bitget_derivatives_data.py"),
        "--panel",
        str(session.panel_path),
    ]
    warmup_end_date = _as_utc(warmup_end).date().isoformat()
    live_end_date = (_as_utc(end) + pd.Timedelta(days=1)).date().isoformat()
    return [
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
            str(session.warmup_mark_dir),
            "--start",
            _as_utc(session.warmup_start).date().isoformat(),
            "--end",
            warmup_end_date,
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
        "latest_signal_day": last_completed_utc_day(_as_utc(now).to_pydatetime()),
        "now": now,
    }


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
    payload, blocked = assess_fn(
        **_assessment_kwargs(session, selection=selection, now=moment)
    )
    commands: list[list[str]] = []
    if backfill and blocked and not dry_run:
        commands = build_backfill_commands(
            session=session,
            selection=selection,
            blocked_members=blocked,
            python=sys.executable,
            oos_start=session.oos_start,
            warmup_end=session.warmup_end,
            end=moment,
        )
        for command in commands:
            completed = runner(command)
            if completed != 0:
                raise RuntimeError(
                    f"top50 backfill command failed ({completed}): {' '.join(command)}"
                )
        payload, blocked = assess_fn(
            **_assessment_kwargs(session, selection=selection, now=moment)
        )

    previous = load_state(session.state_path)
    initialized = bool(previous.get("initialized"))
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
        state["members"] = [str(item["coin_id"]) for item in payload["members"]]
        state["top20"] = [str(item["coin_id"]) for item in payload["top20"]]
        state["member_status"] = {
            str(item["coin_id"]): str(item["status"])
            for item in payload["members"]
        }
        queue_notification_events(state, events)
        notification_failures: list[str] = []
        if notify:
            notifications = state["notifications"]
            assert isinstance(notifications, dict)
            pending = dict(notifications.get("pending", {}))
            for key in sorted(pending):
                event = pending[key]
                if not isinstance(event, dict):
                    continue
                try:
                    send_message(format_event_message(event))
                except Exception as exc:  # noqa: BLE001 - persisted for retry
                    notification_failures.append(str(key))
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
        write_state(session.state_path, state)
        if notification_failures:
            raise RuntimeError(
                "Telegram delivery failed for: " + ", ".join(notification_failures)
            )

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
    lock_file = None
    if not args.dry_run and not args.no_lock:
        from filelock import FileLock, Timeout

        lock = FileLock(str(args.lock_file))
        try:
            lock.acquire(timeout=float(args.wait_seconds))
        except Timeout:
            print(
                f"another execution/refresh holds {args.lock_file}; skipping",
                file=sys.stderr,
            )
            return 0
        lock_file = lock
    try:
        if panel_lags_last_completed_day(args.panel, moment.to_pydatetime()):
            raise SystemExit(
                "panel does not carry the last completed UTC day for "
                f"{moment.isoformat()}: {args.panel}"
            )
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
        result = run_readiness_cycle(
            session=session,
            now=moment,
            notify=bool(args.notify),
            dry_run=bool(args.dry_run),
            backfill=not bool(args.no_backfill),
            runner=lambda command: _run_subprocess(command, cwd=session.project_root),
            send_message=lambda message: _send_telegram(message, moment=moment),
        )
    finally:
        if lock_file is not None:
            lock_file.release()

    payload = result["payload"]
    if isinstance(payload, dict):
        print(
            "top50 readiness: "
            f"{'READY' if payload.get('ready') else 'BLOCKED'} "
            f"as_of={payload.get('as_of')} "
            f"blocked={len(result.get('blocked', []))}"
        )
    return 0 if bool(result["payload"].get("ready")) else 1


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
