"""Weekly featured digest scheduling."""

from __future__ import annotations

from datetime import timezone
import json
import logging
import os
from typing import Any

from filelock import FileLock, Timeout
from sqlmodel import Session, col, select

from atlas20.api.db.models import ReportFile, Run
from atlas20.api.repositories import KvRepo
from atlas20.api._time import utc_now
from atlas20.api.settings import Settings, get_settings
from atlas20.api.services_report import generate_run_report_with_warnings
from atlas20.api.worker.main import session_scope

logger = logging.getLogger(__name__)
DEFAULT_DIGEST_FORMATS = {"markdown", "pdf", "png", "bundle"}


def _attach_lock_release(scheduler: Any, lock: FileLock) -> Any:
    original_shutdown = scheduler.shutdown
    released = False

    def shutdown(*args: Any, **kwargs: Any) -> Any:
        nonlocal released
        try:
            return original_shutdown(*args, **kwargs)
        finally:
            if not released:
                lock.release()
                released = True

    scheduler.shutdown = shutdown
    scheduler._atlas20_scheduler_lock = lock
    return scheduler


def _pick_completed_run(session: Session, week: int) -> Run | None:
    offset = max(0, week)
    stmt = (
        select(Run)
        .where(Run.status == "completed")
        .order_by(col(Run.created_at).desc(), col(Run.run_id).desc())
        .offset(offset)
        .limit(1)
    )
    return session.exec(stmt).first()


def _generate_featured_digest(
    session: Session,
    settings: Settings,
    *,
    week: int = 0,
    formats: set[str] | None = None,
) -> list[ReportFile]:
    run = _pick_completed_run(session, week)
    if run is None:
        logger.info("No completed run available for featured digest generation")
        return []
    result = generate_run_report_with_warnings(
        run.run_id,
        formats or DEFAULT_DIGEST_FORMATS,
        session=session,
        settings=settings,
    )
    for warning in result.warnings:
        logger.warning("Featured digest generation warning for %s: %s", run.run_id, warning)
    KvRepo(session).set("featured_digest_run_id", run.run_id)
    return result.files


def generate_featured_digest(
    *,
    week: int = 0,
    session: Session | None = None,
    formats: set[str] | None = None,
) -> list[ReportFile]:
    settings = get_settings()
    if session is not None:
        return _generate_featured_digest(session, settings, week=week, formats=formats)
    with session_scope(settings) as scoped_session:
        return _generate_featured_digest(scoped_session, settings, week=week, formats=formats)


def _acquire_scheduler_lock(settings: Settings) -> FileLock | None:
    """Take the single-process scheduler lock, or None if another holds it."""
    settings.data_root.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(settings.data_root / ".scheduler.lock"), timeout=0)
    try:
        lock.acquire()
    except Timeout:
        logger.info("scheduler lock held by another worker; skipping")
        return None
    return lock


def _queue_universe_refresh(session: Session, settings: Settings) -> str:
    """Queue a data refresh unless one is already pending."""
    del settings
    existing = session.exec(
        select(Run).where(
            Run.strategy == "universe_refresh",
            col(Run.status).in_(("queued", "running")),
        )
    ).first()
    if existing is not None:
        logger.info("Skipping daily refresh; run %s is already %s", existing.run_id, existing.status)
        return existing.run_id

    from atlas20.api.repositories import RunsRepo

    repo = RunsRepo(session)
    run = repo.create_with_unique_id(
        {
            "strategy": "universe_refresh",
            "universe": "Top-20",
            "window_start": utc_now().date(),
            "window_end": utc_now().date(),
            "status": "queued",
            "params": json.dumps({"kind": "universe_refresh"}),
        }
    )
    logger.info("Queued daily universe refresh as %s", run.run_id)
    return run.run_id


def run_daily_refresh(settings: Settings | None = None) -> str:
    """Queue a daily data refresh so new listings enter the universe."""
    settings = settings or get_settings()
    with session_scope(settings) as session:
        return _queue_universe_refresh(session, settings)


def _build_scheduler() -> Any | None:
    """Construct the APScheduler instance, or None when unavailable."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError as exc:
        logger.warning("APScheduler unavailable; scheduled jobs disabled: %s", exc)
        return None
    return AsyncIOScheduler(timezone=timezone.utc)


def start_scheduler(settings: Settings | None = None, scheduler_factory: Any | None = None) -> Any | None:
    if os.environ.get("ATLAS20_DISABLE_SCHEDULER") == "1":
        return None
    settings = settings or get_settings()

    scheduler = (scheduler_factory or _build_scheduler)()
    if scheduler is None:
        return None

    lock = _acquire_scheduler_lock(settings)
    if lock is None:
        return None
    try:
        scheduler.add_job(
            generate_featured_digest,
            "cron",
            day_of_week="mon",
            hour=0,
            minute=0,
            id="weekly_featured_digest",
            replace_existing=True,
        )
        if settings.daily_refresh_enabled:
            scheduler.add_job(
                run_daily_refresh,
                "cron",
                hour=settings.daily_refresh_hour_utc,
                minute=settings.daily_refresh_minute_utc,
                id="daily_universe_refresh",
                replace_existing=True,
            )
        scheduler.start()
    except Exception:
        lock.release()
        raise
    logger.info("Started weekly featured digest scheduler for report root %s", settings.report_root)
    return _attach_lock_release(scheduler, lock)
