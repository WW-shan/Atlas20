"""Preflight gates for the daily live derivatives chain.

``ops/run_derivatives_daily.sh`` runs the panel refresh, the Bitget mark
refresh, the frozen target book and the real order placement in one launchd
job, because the executor refuses to trade when the book was not evaluated
through the newest completed day.  That guard is correct, but on its own it
turns two ordinary events into a silently skipped rebalance:

* a shutdown or reboot in the middle of the panel refresh leaves
  ``data/processed/panel_daily.csv`` a day behind while the Bitget marks keep
  moving (this happened on 2026-10-16: the machine went down at 10:34, the
  panel stayed on 10-14, and the 11:05 trade job failed closed);
* the machine can simply be off at the scheduled fire time, so the day is
  never attempted at all.

This module holds the two decisions the wrapper needs, as pure functions so
they can be tested without launchd, a network, or an account:

1. :func:`panel_lags_last_completed_day` - is the panel the strategy reads
   still missing the last completed UTC day?  If so the wrapper refreshes it
   once before spending money.
2. :func:`within_run_window` plus :func:`run_day_already_done` - should the
   chain run at all right now?  This lets the job be loaded at boot
   (``RunAtLoad``) without either trading twice or trading outside the
   bounded catch-up window after the model's T+1 fill point.

Nothing here weakens the executor's own guards: they remain the final
backstop and still fail closed.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

#: The frozen spec's T+1 fill point, in UTC.  ops/com.atlas20.derivatives-execute.plist
#: fires five minutes later (11:05 Beijing); tests/test_launchd_derivatives_schedule.py
#: pins the local-to-UTC conversion.
DEFAULT_SCHEDULED_UTC = time(3, 5)

#: How long after the fill point a missed run may still be caught up.  Beyond
#: this the rebalance is skipped and the 19:00 monitor reports the gap, because
#: executing a daily signal many hours late is a different trade.
DEFAULT_CATCHUP_HOURS = 6.0

PANEL_FILENAME = "panel_daily.csv"


def as_utc(moment: datetime) -> datetime:
    """Return ``moment`` in UTC, treating a naive value as already UTC."""

    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def last_completed_utc_day(now: datetime) -> date:
    """The newest day whose UTC bar has closed."""

    return as_utc(now).date() - timedelta(days=1)


def panel_end_date(panel_path: Path) -> date | None:
    """Newest date in a processed panel, or ``None`` when it cannot be read."""

    path = Path(panel_path)
    if not path.is_file():
        return None
    try:
        frame = pd.read_csv(path, usecols=["date"])
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None
    if frame.empty:
        return None
    dates = pd.to_datetime(frame["date"], utc=True, format="mixed", errors="coerce").dropna()
    if dates.empty:
        return None
    return dates.max().date()


def panel_lags_last_completed_day(panel_path: Path, now: datetime) -> bool:
    """True when the panel is missing the last completed UTC day."""

    end = panel_end_date(panel_path)
    if end is None:
        return True
    return end < last_completed_utc_day(now)


def run_day_already_done(state_path: Path, run_day: date) -> bool:
    """True when the executor already recorded a successful run for ``run_day``.

    The executor keys idempotency on ``spec|signal_date|run_day`` and only
    skips a repeat when the previous status was ``ok``, so a failed day must
    stay retryable here too.
    """

    path = Path(state_path)
    if not path.is_file():
        return False
    try:
        state: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(state, dict) or state.get("last_status") != "ok":
        return False
    parts = str(state.get("last_key") or "").split("|")
    if len(parts) < 3:
        return False
    return parts[-1] == run_day.isoformat()


def within_run_window(
    now: datetime,
    *,
    scheduled_utc: time = DEFAULT_SCHEDULED_UTC,
    catchup_hours: float = DEFAULT_CATCHUP_HOURS,
) -> tuple[bool, str]:
    """Whether ``now`` is inside today's trading window, with a reason."""

    moment = as_utc(now)
    opens = datetime.combine(moment.date(), scheduled_utc, tzinfo=timezone.utc)
    if moment < opens:
        return False, f"before the {scheduled_utc:%H:%M} UTC fill window"
    closes = opens + timedelta(hours=float(catchup_hours))
    if moment > closes:
        return False, (
            f"past the {float(catchup_hours):g}h catch-up window "
            f"(it closed {closes:%Y-%m-%d %H:%M} UTC)"
        )
    return True, "inside the run window"
