"""Runs repository."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import case, func, or_, text, update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from atlas20.api._metrics import TERMINAL_BACKTEST_STATUSES, record_backtest_terminal
from atlas20.api._time import utc_now
from atlas20.api.db.models import Run

RUN_FAMILY_CHIPS = {"ATLAS", "Momentum", "MeanRev", "Carry", "Other"}
RUN_STATUS_CHIPS = {"queued", "running", "completed", "failed", "cancelled"}


def terminal_duration_seconds(run: Run) -> float | None:
    if run.duration_s is not None:
        return float(run.duration_s)
    # Worker-written duration_s is authoritative when present.
    # Otherwise use started_at to derive an upper-bound proxy for finished_at
    # at the point the terminal update is committed.
    # If neither timestamp is available, return None so the histogram stays
    # silent rather than recording a misleading zero.
    if run.started_at is None:
        return None
    return (utc_now() - run.started_at).total_seconds()


def _record_terminal_transition(previous_status: str | None, run: Run | None) -> None:
    if run is None or run.status not in TERMINAL_BACKTEST_STATUSES:
        return
    if previous_status in TERMINAL_BACKTEST_STATUSES:
        return
    record_backtest_terminal(run.status, terminal_duration_seconds(run))


class RunsRepo:
    def __init__(self, session: Session):
        self._s = session

    def list(
        self,
        *,
        q: str = "",
        chips: tuple[str, ...] | list[str] = (),
        date_cutoff: date | None = None,
        page: int = 1,
        page_size: int = 14,
    ) -> tuple[list[Run], int]:
        filters = self._filters(q=q, chips=chips, date_cutoff=date_cutoff)
        count_stmt = select(func.count()).select_from(Run)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = int(self._s.exec(count_stmt).one())
        safe_page = max(page, 1)
        safe_page_size = max(page_size, 1)
        stmt = (
            select(Run)
            .where(*filters)
            .order_by(Run.created_at.desc(), Run.run_id.desc())
            .offset((safe_page - 1) * safe_page_size)
            .limit(safe_page_size)
        )
        return list(self._s.exec(stmt).all()), total

    def get(self, run_id: str) -> Run | None:
        return self._s.exec(select(Run).where(Run.run_id == run_id)).first()

    def create(self, run: Run) -> Run:
        self._s.add(run)
        self._s.flush()
        self._s.refresh(run)
        return run

    def create_with_unique_id(self, base_attrs: dict[str, Any]) -> Run:
        for _attempt in range(3):
            self._begin_immediate_for_sqlite()
            run_id = self._compute_next_btk_id()
            try:
                run = Run(run_id=run_id, **base_attrs)
                self._s.add(run)
                self._s.flush()
                return run
            except IntegrityError:
                self._s.rollback()
                continue
        raise RuntimeError("could not allocate unique run_id after 3 attempts")

    def _begin_immediate_for_sqlite(self) -> None:
        """Promote SQLite read-transaction to write-transaction immediately.

        Why: SQLite's default 'deferred' mode delays acquiring the reserved lock
        until first write, creating a TOCTOU window in MAX+1 id allocation.
        BEGIN IMMEDIATE acquires the lock at transaction start, serializing
        concurrent inserts across SEPARATE sessions/connections.

        Within a single session reused across calls, this helper short-circuits
        via in_transaction() -- the outer scope already holds the write lock.
        The race we guard against is cross-session, not intra-session.
        """
        if self._s.in_transaction():
            return
        if self._s.get_bind().dialect.name == "sqlite":
            self._s.exec(text("BEGIN IMMEDIATE"))

    def update(self, run_id: str, **fields: object) -> Run | None:
        run = self.get(run_id)
        if run is None:
            return None
        previous_status = run.status
        for key, value in fields.items():
            if hasattr(run, key):
                setattr(run, key, value)
        self._s.add(run)
        self._s.flush()
        self._s.refresh(run)
        _record_terminal_transition(previous_status, run)
        return run

    def update_metrics_from_completion(
        self,
        run_id: str,
        *,
        return_pct: float | None = None,
        sharpe: float | None = None,
        max_dd: float | None = None,
        duration_s: int | None = None,
        status: str = "completed",
        error: str | None = None,
        eta_s: int | None = None,
        worker_pid: int | None = None,
        heartbeat_at: datetime | None = None,
    ) -> Run | None:
        current = self.get(run_id)
        previous_status = current.status if current is not None else None
        if status == "completed" and duration_s is None:
            raise ValueError("duration_s is required for completed runs")
        fields: dict[str, object] = {
            "status": status,
            "error": error,
            "eta_s": eta_s,
            "worker_pid": worker_pid,
            "heartbeat_at": heartbeat_at,
        }
        if status == "completed":
            fields.update(
                {
                    "return_pct": return_pct,
                    "sharpe": sharpe,
                    "max_dd": max_dd,
                    "duration_s": duration_s,
                }
            )
        if status in {"completed", "failed"}:
            if error:
                cancel_error = f"cancelled during execution (would have been {status}: {error})"
            else:
                cancel_error = f"cancelled during execution (would have been {status})"
            fields["status"] = case((Run.requested_cancel.is_(True), "cancelled"), else_=status)
            fields["error"] = case((Run.requested_cancel.is_(True), cancel_error), else_=error)

        result = self._s.exec(
            sa_update(Run)
            .where(Run.run_id == run_id)
            .values(**fields)
            .execution_options(synchronize_session=False)
        )
        self._s.flush()
        if result.rowcount == 0:
            return None
        self._s.expire_all()
        updated = self.get(run_id)
        _record_terminal_transition(previous_status, updated)
        return updated

    def request_cancel(self, run_id: str) -> Run | None:
        self._s.exec(
            sa_update(Run)
            .where(Run.run_id == run_id, Run.status.in_(("queued", "running")))
            .values(requested_cancel=True)
            .execution_options(synchronize_session=False)
        )
        self._s.flush()
        self._s.expire_all()
        return self.get(run_id)

    def toggle_favorite(self, run_id: str) -> Run | None:
        run = self.get(run_id)
        if run is None:
            return None
        run.favorited = not run.favorited
        self._s.add(run)
        self._s.flush()
        self._s.refresh(run)
        return run

    def list_queue(self) -> list[Run]:
        stmt = (
            select(Run)
            .where(Run.status.in_(("queued", "running")))
            .order_by(Run.created_at.desc(), Run.run_id.desc())
        )
        return list(self._s.exec(stmt).all())

    def next_btk_id(self) -> str:
        """Deprecated: only use for non-concurrent call paths."""
        return self._compute_next_btk_id()

    def _compute_next_btk_id(self) -> str:
        ids = self._s.exec(select(Run.run_id).where(Run.run_id.like("btk_%"))).all()
        max_number = 0
        for run_id in ids:
            try:
                max_number = max(max_number, int(run_id.rsplit("_", 1)[1]))
            except (IndexError, ValueError):
                continue
        return f"btk_{max_number + 1:04d}"

    def _filters(
        self,
        *,
        q: str,
        chips: tuple[str, ...] | list[str],
        date_cutoff: date | None,
    ) -> list[object]:
        filters: list[object] = []
        if q:
            pattern = f"%{q.lower()}%"
            filters.append(
                or_(
                    func.lower(Run.strategy).like(pattern),
                    func.lower(Run.run_id).like(pattern),
                    func.lower(Run.universe).like(pattern),
                    func.lower(Run.strategy_family).like(pattern),
                )
            )
        for chip in [item for item in chips if item]:
            if chip == "favorited":
                filters.append(Run.favorited.is_(True))
            elif chip in RUN_STATUS_CHIPS:
                filters.append(Run.status == chip)
            elif chip in RUN_FAMILY_CHIPS:
                filters.append(Run.strategy_family == chip)
            else:
                filters.append(func.lower(Run.strategy).like(f"%{chip.lower()}%"))
        if date_cutoff is not None:
            cutoff = datetime.combine(date_cutoff, time.min, tzinfo=timezone.utc)
            filters.append(Run.created_at >= cutoff)
        return filters
