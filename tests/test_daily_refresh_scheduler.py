"""Daily data refresh scheduling.

Raw provider caches go stale on their own, but nothing triggers a refresh on a
schedule. Operators should be able to enable a daily job that queues a universe
refresh without hand-editing cron.
"""

from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path

from atlas20.api import scheduler as scheduler_module
from atlas20.api._time import utc_now
from atlas20.api.settings import Settings


class _FakeScheduler:
    def __init__(self, *args, **kwargs) -> None:
        self.jobs: list[dict[str, object]] = []
        self.started = False
        self.shutdown_calls = 0

    def add_job(self, func, trigger, **kwargs) -> None:
        self.jobs.append({"func": func, "trigger": trigger, **kwargs})

    def start(self) -> None:
        self.started = True

    def shutdown(self, *args, **kwargs) -> None:
        self.shutdown_calls += 1


def _install_fake(monkeypatch) -> dict[str, _FakeScheduler]:
    """Patch AsyncIOScheduler at its definition site.

    ``start_scheduler`` imports it inside the function body, so the attribute
    on the source module is what must be replaced.
    """
    created: dict[str, _FakeScheduler] = {}

    class _Scheduler(_FakeScheduler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            created["scheduler"] = self

    created["factory"] = _Scheduler  # type: ignore[assignment]
    return created


def test_daily_refresh_job_registered_when_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ATLAS20_DISABLE_SCHEDULER", raising=False)
    created = _install_fake(monkeypatch)
    monkeypatch.setattr(scheduler_module, "_acquire_scheduler_lock", lambda settings: object())
    monkeypatch.setattr(scheduler_module, "_attach_lock_release", lambda sched, lock: sched)

    settings = Settings(
        data_root=tmp_path,
        report_root=tmp_path / "reports",
        daily_refresh_enabled=True,
        daily_refresh_hour_utc=2,
        daily_refresh_minute_utc=30,
    )

    scheduler_module.start_scheduler(settings, scheduler_factory=created["factory"])

    jobs = {job["id"]: job for job in created["scheduler"].jobs}
    assert "weekly_featured_digest" in jobs
    assert "daily_universe_refresh" in jobs
    assert "data_freshness_watchdog" in jobs
    daily = jobs["daily_universe_refresh"]
    assert daily["hour"] == 2
    assert daily["minute"] == 30


def test_daily_refresh_job_absent_when_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ATLAS20_DISABLE_SCHEDULER", raising=False)
    created = _install_fake(monkeypatch)
    monkeypatch.setattr(scheduler_module, "_acquire_scheduler_lock", lambda settings: object())
    monkeypatch.setattr(scheduler_module, "_attach_lock_release", lambda sched, lock: sched)

    settings = Settings(
        data_root=tmp_path,
        report_root=tmp_path / "reports",
        daily_refresh_enabled=False,
    )

    scheduler_module.start_scheduler(settings, scheduler_factory=created["factory"])

    jobs = {job["id"] for job in created["scheduler"].jobs}
    assert "daily_universe_refresh" not in jobs
    assert "data_freshness_watchdog" in jobs


def test_daily_refresh_skips_when_refresh_already_queued(tmp_path, monkeypatch) -> None:
    """Repeated ticks must not pile up duplicate refresh runs."""
    calls: list[str] = []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def commit(self):
            calls.append("commit")

        def rollback(self):
            pass

    monkeypatch.setattr(scheduler_module, "session_scope", lambda settings: _Session())
    monkeypatch.setattr(
        scheduler_module,
        "_queue_universe_refresh",
        lambda session, settings: calls.append("queued"),
    )

    settings = Settings(data_root=tmp_path, report_root=tmp_path / "reports")
    scheduler_module.run_daily_refresh(settings)

    assert calls == ["queued"]


def _write_heartbeat(root: Path, primary: str | None) -> None:
    (root / "data_freshness.json").write_text(
        json.dumps({"status": "completed", "latest_primary_date": primary, "checked_at": utc_now().isoformat()}),
        encoding="utf-8",
    )


def _enabled_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path,
        report_root=tmp_path / "reports",
        daily_refresh_enabled=True,
        daily_refresh_hour_utc=2,
        daily_refresh_minute_utc=30,
    )


def test_daily_refresh_catchup_job_registered_after_the_first_attempt(tmp_path, monkeypatch) -> None:
    """One missed publication must not cost a whole day of stale ranks."""
    monkeypatch.delenv("ATLAS20_DISABLE_SCHEDULER", raising=False)
    created = _install_fake(monkeypatch)
    monkeypatch.setattr(scheduler_module, "_acquire_scheduler_lock", lambda settings: object())
    monkeypatch.setattr(scheduler_module, "_attach_lock_release", lambda sched, lock: sched)

    scheduler_module.start_scheduler(_enabled_settings(tmp_path), scheduler_factory=created["factory"])

    jobs = {job["id"]: job for job in created["scheduler"].jobs}
    catchup = jobs["daily_universe_refresh_catchup"]
    assert catchup["hour"] == 6, "the retry must land a few hours after the scheduled run"
    assert catchup["minute"] == 30


def test_catchup_skips_when_yesterdays_close_is_already_on_disk(tmp_path, monkeypatch) -> None:
    today = utc_now().date()
    _write_heartbeat(tmp_path, (today - timedelta(days=1)).isoformat())
    queue = _recording_queue(monkeypatch)

    result = scheduler_module.run_daily_refresh_catchup(_enabled_settings(tmp_path))

    assert result is None
    assert queue == [], "a current feed must not pay for a redundant refresh"


def test_catchup_queues_when_the_feed_is_a_day_behind(tmp_path, monkeypatch) -> None:
    today = utc_now().date()
    _write_heartbeat(tmp_path, (today - timedelta(days=2)).isoformat())
    queue = _recording_queue(monkeypatch)

    result = scheduler_module.run_daily_refresh_catchup(_enabled_settings(tmp_path))

    assert result == "queued"
    assert queue == ["queued"]


def _recording_queue(monkeypatch) -> list[str]:
    queued: list[str] = []

    def _fake(settings=None):
        queued.append("queued")
        return "queued"

    monkeypatch.setattr(scheduler_module, "run_daily_refresh", _fake)
    return queued
