"""Weekly featured digest scheduling."""

from __future__ import annotations

from datetime import timezone
import logging
import os

from filelock import FileLock, Timeout
from sqlmodel import Session, select

from atlas20.api.db.models import ReportFile, Run
from atlas20.api.repositories import KvRepo
from atlas20.api.settings import Settings, get_settings
from atlas20.api.services_report import generate_run_report_with_warnings
from atlas20.api.worker.main import session_scope

logger = logging.getLogger(__name__)
DEFAULT_DIGEST_FORMATS = {"markdown", "pdf", "png", "bundle"}


def _attach_lock_release(scheduler, lock: FileLock):
    original_shutdown = scheduler.shutdown
    released = False

    def shutdown(*args, **kwargs):
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
        .order_by(Run.created_at.desc(), Run.run_id.desc())
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


def start_scheduler(settings: Settings | None = None):
    if os.environ.get("ATLAS20_DISABLE_SCHEDULER") == "1":
        return None
    settings = settings or get_settings()
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError as exc:
        logger.warning("APScheduler unavailable; weekly featured digest scheduler disabled: %s", exc)
        return None

    settings.data_root.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(settings.data_root / ".scheduler.lock"), timeout=0)
    try:
        lock.acquire()
    except Timeout:
        logger.info("scheduler lock held by another worker; skipping")
        return None

    scheduler = AsyncIOScheduler(timezone=timezone.utc)
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
        scheduler.start()
    except Exception:
        lock.release()
        raise
    logger.info("Started weekly featured digest scheduler for report root %s", settings.report_root)
    return _attach_lock_release(scheduler, lock)
