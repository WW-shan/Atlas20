"""Restart recovery for runs abandoned by dead workers."""

from __future__ import annotations

from datetime import timedelta

import structlog
from sqlalchemy import or_
from sqlmodel import Session, select

from atlas20.api._metrics import record_backtest_terminal
from atlas20.api._time import utc_now
from atlas20.api.db.models import Run
from atlas20.api.repositories.runs_repo import terminal_duration_seconds

logger = structlog.get_logger(__name__)


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
        duration = terminal_duration_seconds(run)
        run.status = "failed"
        run.error = STALE_HEARTBEAT_ERROR
        record_backtest_terminal("failed", duration)
        logger.info(
            "backtest.terminal",
            run_id=run.run_id,
            previous_status="running",
            status=run.status,
            duration_s=duration,
            strategy=run.strategy,
        )
        run.worker_pid = None
        run.heartbeat_at = None
        session.add(run)
    session.flush()
    return len(stale_runs)


def recover_runs_owned_by_pid(session: Session, my_pid: int) -> int:
    """Recover running rows whose recorded worker_pid equals my_pid.

    On a normal restart this returns 0 because the new PID differs from the
    dead worker's PID. Use recover_stale_runs for the general restart case.
    """
    runs = session.exec(
        select(Run).where(Run.status == "running", Run.worker_pid == my_pid)
    ).all()
    count = 0
    for run in runs:
        duration = terminal_duration_seconds(run)
        run.status = "failed"
        run.error = RESTART_RECOVERY_ERROR
        record_backtest_terminal("failed", duration)
        logger.info(
            "backtest.terminal",
            run_id=run.run_id,
            previous_status="running",
            status=run.status,
            duration_s=duration,
            strategy=run.strategy,
        )
        session.add(run)
        count += 1
    session.commit()
    return count
