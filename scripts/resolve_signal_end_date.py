"""Resolve the newest fully evaluable signal day for the LS104 ledger.

The live signal needs both the point-in-time panel and the execution-hour mark
for D+1 01:05.  When the UTC day has just rolled over, the panel may still be
D-2 while the mark tree already carries D-1; pinning the ledger to D-1 would
make the data audit fail and, worse, could hide the last evaluated date.  This
helper returns the newest day for which both inputs are actually present so a
manual/audit rebuild stays reproducible without `--allow-stale`.
"""

from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _panel_last_day(path: Path) -> pd.Timestamp:
    frame = pd.read_csv(path, usecols=["date"])
    if frame.empty:
        raise ValueError(f"panel has no rows: {path}")
    values = pd.to_datetime(frame["date"], utc=True, errors="coerce").dropna()
    if values.empty:
        raise ValueError(f"panel has no valid dates: {path}")
    return pd.Timestamp(values.max()).normalize()


def _last_mark(raw_dir: Path) -> pd.Timestamp:
    candle_dir = Path(raw_dir) / "candles"
    latest: pd.Timestamp | None = None
    for path in sorted(candle_dir.glob("*_mark.csv")):
        try:
            frame = pd.read_csv(path, usecols=["open_time"])
        except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
            continue
        if frame.empty:
            continue
        values = pd.to_datetime(
            frame["open_time"], utc=True, format="mixed", errors="coerce"
        ).dropna()
        if values.empty:
            continue
        candidate = pd.Timestamp(values.max())
        if latest is None or candidate > latest:
            latest = candidate
    if latest is None:
        raise ValueError(f"no mark candles under {candle_dir}")
    return latest


def resolve_signal_end_date(
    *,
    panel: Path,
    raw_dir: Path,
    execution_utc: time = time(1, 5),
    now: datetime | None = None,
) -> pd.Timestamp:
    panel_last = _panel_last_day(panel)
    last_mark = _last_mark(raw_dir)
    moment = pd.Timestamp(now or datetime.now(timezone.utc))
    if moment.tzinfo is None:
        moment = moment.tz_localize("UTC")
    else:
        moment = moment.tz_convert("UTC")
    last_completed = moment.normalize() - pd.Timedelta(days=1)
    # Before the 01:05 fill, the panel can already carry the last completed
    # day while only the 00:00 mark exists.  In that one case the target
    # ledger is final and only the newest signal's execution price is
    # provisional; the signal script records that explicitly.
    if panel_last >= last_completed and last_mark >= last_completed:
        return panel_last
    required_clock = datetime.combine(
        last_mark.date(), execution_utc, tzinfo=timezone.utc
    )
    if last_mark >= pd.Timestamp(required_clock):
        mark_signal_day = pd.Timestamp(last_mark.date(), tz="UTC") - pd.Timedelta(days=1)
    else:
        mark_signal_day = pd.Timestamp(last_mark.date(), tz="UTC") - pd.Timedelta(days=2)
    return min(panel_last, mark_signal_day)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=PROJECT_ROOT / "data/processed/panel_daily.csv")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=PROJECT_ROOT / "data/raw/bitget_derivatives/merged_oos_20261112",
    )
    parser.add_argument("--execution-utc", default="01:05")
    parser.add_argument("--now", default=None)
    args = parser.parse_args(argv)
    try:
        hour, minute = (int(part) for part in str(args.execution_utc).split(":", 1))
        execution_utc = time(hour, minute)
    except ValueError as exc:
        parser.error(f"--execution-utc must be HH:MM: {exc}")
    try:
        now = (
            datetime.fromisoformat(str(args.now).replace("Z", "+00:00"))
            if args.now
            else None
        )
        resolved = resolve_signal_end_date(
            panel=args.panel,
            raw_dir=args.raw_dir,
            execution_utc=execution_utc,
            now=now,
        )
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(resolved.date().isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
