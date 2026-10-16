"""Answer the two questions the live chain must settle before it trades.

Used by ``ops/run_derivatives_daily.sh``:

* ``--check window`` - may the chain run right now?  Exits 0 inside the
  bounded catch-up window when today's run day has not already completed,
  and 3 otherwise.  The job is loaded at boot (``RunAtLoad``) so a reboot
  after the fill point catches the day up, and this gate is what keeps that
  from becoming a second trade or an out-of-hours one.
* ``--check panel`` - does ``data/processed/panel_daily.csv`` carry the last
  completed UTC day?  Exits 0 when it does and 3 when it lags, which is the
  signal for the wrapper to refresh before spending money.

Exit code 3 (not 1) is deliberate: it means "a documented reason says do not
trade", as opposed to a crash, so the wrapper can skip quietly and still let
a real error abort the job.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.live_chain import (  # noqa: E402
    DEFAULT_CATCHUP_HOURS,
    DEFAULT_SCHEDULED_UTC,
    as_utc,
    last_completed_utc_day,
    panel_end_date,
    panel_lags_last_completed_day,
    run_day_already_done,
    within_run_window,
)

BLOCKED = 3
DEFAULT_PANEL = PROJECT_ROOT / "data" / "processed" / "panel_daily.csv"
DEFAULT_STATE_FILE = PROJECT_ROOT / "data" / "derivatives_execution_state.json"


def _parse_clock(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))
    except ValueError as exc:  # pragma: no cover - argparse reports the usage
        raise argparse.ArgumentTypeError(f"{value!r} is not HH:MM") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", choices=("window", "panel"), default="window")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--scheduled-utc", type=_parse_clock, default=DEFAULT_SCHEDULED_UTC)
    parser.add_argument("--catchup-hours", type=float, default=DEFAULT_CATCHUP_HOURS)
    parser.add_argument(
        "--now",
        default=None,
        help="ISO-8601 UTC timestamp to evaluate against (default: the real clock)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore the run window and the same-day idempotency record",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = (
        as_utc(datetime.fromisoformat(args.now))
        if args.now
        else datetime.now(timezone.utc)
    )

    if args.check == "window":
        if args.force:
            return 0
        if run_day_already_done(args.state_file, now.date()):
            print(f"run day {now.date().isoformat()} already completed; nothing to do")
            return BLOCKED
        allowed, reason = within_run_window(
            now, scheduled_utc=args.scheduled_utc, catchup_hours=float(args.catchup_hours)
        )
        if not allowed:
            print(f"{reason}; not trading")
            return BLOCKED
        print(f"{reason}; proceeding")
        return 0

    end = panel_end_date(args.panel)
    expected = last_completed_utc_day(now)
    if args.force:
        return 0
    if panel_lags_last_completed_day(args.panel, now):
        print(f"panel ends {end or 'missing'} but {expected.isoformat()} is the last completed UTC day")
        return BLOCKED
    print(f"panel carries {expected.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
