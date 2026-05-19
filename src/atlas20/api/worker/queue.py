"""SQLite-backed worker queue claim logic."""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlmodel import Session, select

from atlas20.api._time import utc_now
from atlas20.api.db.models import Run


class WorkerQueue:
    def __init__(self, session: Session):
        self._s = session

    def claim_one(self) -> Run | None:
        self._begin_immediate_for_sqlite()
        candidate = self._s.exec(
            select(Run).where(Run.status == "queued").order_by(Run.created_at.asc()).limit(1)
        ).first()
        if candidate is None:
            self._s.commit()
            return None

        now = utc_now()
        candidate.status = "running"
        candidate.worker_pid = os.getpid()
        candidate.started_at = now
        candidate.heartbeat_at = now
        self._s.add(candidate)
        self._s.commit()
        self._s.refresh(candidate)
        return candidate

    def _begin_immediate_for_sqlite(self) -> None:
        if self._s.in_transaction():
            return
        if self._s.get_bind().dialect.name == "sqlite":
            self._s.exec(text("BEGIN IMMEDIATE"))
