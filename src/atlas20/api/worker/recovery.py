"""Restart recovery for runs abandoned by dead workers."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import or_
from sqlmodel import Session, select

from atlas20.api._time import utc_now
from atlas20.api.db.models import Run


STALE_HEARTBEAT_ERROR = "worker died - heartbeat stale"
RESTART_RECOVERY_ERROR = "worker died — restart recovery"


def recover_stale_runs(session: Session, stale_after_seconds: int = 60) -> int:
    cutoff = utc_now() - timedelta(seconds=stale_after_seconds)
    stale_runs = session.exec(
        select(Run).where(
            Run.status == "running",
            or_(Run.heartbeat_at.is_(None), Run.heartbeat_at < cutoff),
        )
    ).all()
    for run in stale_runs:
        run.status = "failed"
        run.error = STALE_HEARTBEAT_ERROR
        run.worker_pid = None
        run.heartbeat_at = None
        session.add(run)
    session.flush()
    return len(stale_runs)


def recover_my_own_stale_runs(session: Session, my_pid: int) -> int:
    runs = session.exec(
        select(Run).where(Run.status == "running", Run.worker_pid == my_pid)
    ).all()
    count = 0
    for run in runs:
        run.status = "failed"
        run.error = RESTART_RECOVERY_ERROR
        session.add(run)
        count += 1
    session.commit()
    return count
