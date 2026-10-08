"""Recovery for runs abandoned by dead workers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import time

from sqlalchemy import or_
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from atlas20.api._time import utc_now
from atlas20.api.db.models import Run
from atlas20.api.repositories.runs_repo import RunsRepo


STALE_HEARTBEAT_ERROR = "worker died - heartbeat stale"
RESTART_RECOVERY_ERROR = "worker died — restart recovery"

# A live worker writes a heartbeat every interval, so a run is orphaned once
# this many consecutive heartbeats are missing. The floor absorbs SQLite busy
# waits and GC pauses when the interval is small.
STALE_HEARTBEAT_MISSES = 15
MIN_STALE_AFTER_SECONDS = 60.0


def stale_threshold_seconds(heartbeat_interval_seconds: float) -> float:
    """How long a heartbeat may stand still before its run counts as orphaned."""
    return max(MIN_STALE_AFTER_SECONDS, STALE_HEARTBEAT_MISSES * heartbeat_interval_seconds)


class StaleRunMonitor:
    """Find running rows whose heartbeat stopped advancing, and fail them.

    Staleness is measured on this process's monotonic clock: a heartbeat value
    that has not changed for ``stale_after_seconds`` since this monitor first
    saw it. Comparing the stored wall-clock heartbeat against this host's
    clock would fail live runs whenever another worker's clock is behind.
    Call ``recover`` periodically; the first call only records what it sees.
    """

    def __init__(self, stale_after_seconds: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._stale_after = stale_after_seconds
        self._clock = clock
        self._unchanged_since: dict[str, tuple[datetime | None, float]] = {}

    def recover(self, session: Session) -> int:
        now = self._clock()
        rows = session.exec(select(Run.run_id, Run.heartbeat_at).where(Run.status == "running")).all()
        observed: dict[str, tuple[datetime | None, float]] = {}
        stale: list[tuple[str, datetime | None]] = []
        for run_id, heartbeat_at in rows:
            previous = self._unchanged_since.get(run_id)
            if previous is None or previous[0] != heartbeat_at:
                observed[run_id] = (heartbeat_at, now)
                continue
            observed[run_id] = previous
            if now - previous[1] >= self._stale_after:
                stale.append((run_id, heartbeat_at))
        self._unchanged_since = observed

        recovered = 0
        for run_id, heartbeat_at in stale:
            # Skip the run if its heartbeat moved after we looked.
            unchanged = (
                col(Run.heartbeat_at).is_(None) if heartbeat_at is None else col(Run.heartbeat_at) <= heartbeat_at
            )
            if _fail_orphan(session, run_id, STALE_HEARTBEAT_ERROR, unchanged):
                recovered += 1
                self._unchanged_since.pop(run_id, None)
        return recovered


def recover_stale_runs(session: Session, stale_after_seconds: float = 60) -> int:
    """Fail running rows whose heartbeat is older than the cutoff by this host's clock.

    Only safe when every worker shares this host's clock; the worker itself
    uses StaleRunMonitor, which does not compare clocks.
    """
    cutoff = utc_now() - timedelta(seconds=stale_after_seconds)
    stale = or_(col(Run.heartbeat_at).is_(None), col(Run.heartbeat_at) < cutoff)
    run_ids = session.exec(select(Run.run_id).where(Run.status == "running", stale)).all()
    recovered = sum(1 for run_id in run_ids if _fail_orphan(session, run_id, STALE_HEARTBEAT_ERROR, stale))
    session.flush()
    return recovered


def recover_runs_owned_by_pid(session: Session, my_pid: int) -> int:
    """Recover running rows whose recorded worker_pid equals my_pid.

    Not used by the worker: PIDs are not unique across hosts or containers
    (every containerised worker is PID 1), so this would fail another live
    worker's runs. The worker relies on StaleRunMonitor instead.
    """
    owned = col(Run.worker_pid) == my_pid
    run_ids = session.exec(select(Run.run_id).where(Run.status == "running", owned)).all()
    count = sum(1 for run_id in run_ids if _fail_orphan(session, run_id, RESTART_RECOVERY_ERROR, owned))
    session.commit()
    return count


def _fail_orphan(session: Session, run_id: str, error: str, still_orphaned: ColumnElement[bool]) -> bool:
    # Conditional on the run still running and still matching the staleness
    # test, so a run that finished or heartbeated meanwhile is left alone. A
    # pending cancel request is honoured: the run ends as cancelled.
    finished = RunsRepo(session).update_metrics_from_completion(
        run_id,
        status="failed",
        error=error,
        heartbeat_at=None,
        worker_pid=None,
        from_statuses=("running",),
        where=(still_orphaned,),
    )
    return finished is not None
