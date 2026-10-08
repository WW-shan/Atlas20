"""The worker must ride out transient database errors instead of exiting."""

from __future__ import annotations

from datetime import date
import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import SQLModel, Session, create_engine

from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo, get_engine
from atlas20.api.settings import Settings, get_settings
from atlas20.api.worker import main as worker_main


@pytest.fixture
def worker_env(tmp_path, monkeypatch):
    db_url = f"sqlite:///{(tmp_path / 'resilience.sqlite').as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setenv("ATLAS20_DB_URL", db_url)
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_WORKER_POLL_INTERVAL_SECONDS", "0.01")
    get_settings.cache_clear()
    shutdown = threading.Event()
    monkeypatch.setattr(worker_main, "_shutdown_requested", shutdown)
    monkeypatch.setattr(worker_main, "setup_signal_handlers", lambda: None)
    monkeypatch.setattr(worker_main, "start_metrics_server", lambda port: None)
    monkeypatch.setattr(worker_main, "_recover_orphaned_runs", lambda settings, monitor, worker_id: 0)
    yield engine, shutdown
    engine.dispose()


def _locked() -> OperationalError:
    return OperationalError("BEGIN IMMEDIATE", {}, Exception("database is locked"))


def test_worker_keeps_polling_after_a_database_error_during_claim(worker_env, monkeypatch) -> None:
    _, shutdown = worker_env
    calls: list[int] = []

    def flaky_claim(self, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise _locked()
        shutdown.set()
        return None

    monkeypatch.setattr(worker_main.WorkerQueue, "claim_one", flaky_claim)

    worker_main.main()

    assert len(calls) == 2


def test_worker_marks_the_run_failed_and_continues_when_execution_errors(worker_env, monkeypatch) -> None:
    engine, shutdown = worker_env
    with Session(engine) as session:
        session.add(
            Run(
                run_id="btk_0001",
                strategy="base",
                universe="Top-5",
                window_start=date(2026, 1, 1),
                window_end=date(2026, 2, 1),
                status="queued",
            )
        )
        session.commit()
    executed: list[str] = []

    def exploding_execute(run_id, settings, **kwargs):
        executed.append(run_id)
        shutdown.set()
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_main, "_execute_run", exploding_execute)

    worker_main.main()

    with Session(engine) as session:
        run = RunsRepo(session).get("btk_0001")
    assert executed == ["btk_0001"]
    assert run is not None
    assert run.status == "failed"
    assert "boom" in str(run.error)


def test_subprocess_is_stopped_when_supervision_cannot_start(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{(tmp_path / 'spawn.sqlite').as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Run(
                run_id="btk_0001",
                strategy="base",
                universe="Top-5",
                window_start=date(2026, 1, 1),
                window_end=date(2026, 2, 1),
                status="running",
            )
        )
        session.commit()
    settings = Settings(db_url=db_url, report_root=tmp_path / "reports", worker_cancel_grace_seconds=0.01)

    class Proc:
        returncode: int | None = None
        terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = -15

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    proc = Proc()
    monkeypatch.setattr(worker_main.subprocess, "Popen", lambda *args, **kwargs: proc)

    def no_thread(*args, **kwargs):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(worker_main, "start_heartbeat_thread", no_thread)

    with pytest.raises(RuntimeError):
        worker_main._execute_run("btk_0001", settings)

    assert proc.terminated is True
    engine.dispose()


def test_sqlite_engine_waits_for_locks_and_uses_wal(tmp_path) -> None:
    settings = Settings(db_url=f"sqlite:///{(tmp_path / 'engine.sqlite').as_posix()}")

    with get_engine(settings).connect() as conn:
        busy_timeout_ms = conn.execute(text("PRAGMA busy_timeout")).scalar_one()
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()

    assert busy_timeout_ms >= 30_000
    assert str(journal_mode).lower() == "wal"
