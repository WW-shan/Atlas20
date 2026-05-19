from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, timedelta
import subprocess
import time

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlmodel import SQLModel, Session, create_engine, select

from atlas20.api.app import create_app
from atlas20.api._time import utc_now
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo, get_session
from atlas20.api.settings import Settings
from atlas20.api.worker.main import _execute_run, start_heartbeat_thread
from atlas20.api.worker.queue import WorkerQueue
from atlas20.api.worker.recovery import recover_stale_runs


def _run(run_id: str, *, status: str = "queued", created_offset: int = 0, heartbeat_offset: int | None = None) -> Run:
    now = utc_now()
    heartbeat_at = None if heartbeat_offset is None else now + timedelta(seconds=heartbeat_offset)
    return Run(
        run_id=run_id,
        strategy="ATLAS Adaptive v3",
        strategy_family="ATLAS",
        universe="Top-20",
        window_start=date(2024, 1, 1),
        window_end=date(2026, 5, 18),
        status=status,
        created_at=now + timedelta(seconds=created_offset),
        heartbeat_at=heartbeat_at,
    )


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'worker.sqlite').as_posix()}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _settings(tmp_path) -> Settings:
    return Settings(
        db_url=f"sqlite:///{(tmp_path / 'worker.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        project_root=tmp_path,
        run_timeout_seconds=1,
        worker_poll_interval_seconds=0.01,
    )


def test_claim_one_returns_oldest_queued_run(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0002", created_offset=20))
        session.add(_run("btk_0001", created_offset=10))
        session.commit()

        claimed = WorkerQueue(session).claim_one()

        assert claimed is not None
        assert claimed.run_id == "btk_0001"


def test_claim_one_skips_already_running(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", status="running", created_offset=10))
        session.add(_run("btk_0002", created_offset=20))
        session.commit()

        claimed = WorkerQueue(session).claim_one()

        assert claimed is not None
        assert claimed.run_id == "btk_0002"


def test_claim_one_returns_none_when_empty(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        assert WorkerQueue(session).claim_one() is None


def test_claim_marks_status_running_and_sets_worker_pid(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001"))
        session.commit()

        claimed = WorkerQueue(session).claim_one()

        assert claimed is not None
        assert claimed.status == "running"
        assert claimed.worker_pid is not None
        assert claimed.started_at is not None
        assert claimed.heartbeat_at is not None


def test_claim_one_skips_queued_with_requested_cancel(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        run = _run("btk_0001")
        run.requested_cancel = True
        session.add(run)
        session.commit()

        claimed = WorkerQueue(session).claim_one()

        cancelled = RunsRepo(session).get("btk_0001")
        assert claimed is None
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.error == "cancelled before execution"
        assert cancelled.started_at is not None
        assert cancelled.heartbeat_at is None


def test_concurrent_claim_from_two_workers_returns_different_runs(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", created_offset=10))
        session.add(_run("btk_0002", created_offset=20))
        session.commit()

    def claim() -> str | None:
        with Session(engine) as session:
            claimed = WorkerQueue(session).claim_one()
            return claimed.run_id if claimed else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        run_ids = list(executor.map(lambda _: claim(), range(2)))

    assert sorted(run_ids) == ["btk_0001", "btk_0002"]


class FakeProcess:
    def __init__(self, returncode: int | None = None):
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        del timeout
        return self.returncode


def test_heartbeat_thread_updates_heartbeat_at(tmp_path):
    engine = _engine(tmp_path)
    settings = _settings(tmp_path)
    old_heartbeat = utc_now() - timedelta(minutes=5)
    with Session(engine) as session:
        run = _run("btk_0001", status="running")
        run.heartbeat_at = old_heartbeat
        session.add(run)
        session.commit()

    process = FakeProcess()
    stop_event, cancelled_event, thread = start_heartbeat_thread(
        "btk_0001",
        process,
        settings,
        heartbeat_interval_seconds=0.01,
    )
    time.sleep(0.05)
    stop_event.set()
    thread.join(timeout=1)

    with Session(engine) as session:
        updated = RunsRepo(session).get("btk_0001")
        assert updated is not None
        assert updated.heartbeat_at is not None
        assert updated.heartbeat_at > old_heartbeat
        assert not cancelled_event.is_set()


def test_cancel_sends_sigterm(tmp_path):
    engine = _engine(tmp_path)
    settings = _settings(tmp_path)
    with Session(engine) as session:
        run = _run("btk_0001", status="running")
        run.requested_cancel = True
        session.add(run)
        session.commit()

    process = FakeProcess()
    stop_event, cancelled_event, thread = start_heartbeat_thread(
        "btk_0001",
        process,
        settings,
        heartbeat_interval_seconds=0.01,
    )
    time.sleep(0.05)
    stop_event.set()
    thread.join(timeout=1)

    with Session(engine) as session:
        cancelled = RunsRepo(session).get("btk_0001")
        assert cancelled is not None
        assert process.terminated is True
        assert cancelled_event.is_set()
        assert cancelled.status == "cancelled"
        assert cancelled.error == "cancelled by user"


def test_cancel_uses_configured_heartbeat_under_one_second(tmp_path):
    engine = _engine(tmp_path)
    settings = _settings(tmp_path)
    settings.worker_heartbeat_interval_seconds = 0.1
    settings.worker_cancel_grace_seconds = 0.1
    with Session(engine) as session:
        run = _run("btk_0001", status="running")
        run.requested_cancel = True
        session.add(run)
        session.commit()

    process = FakeProcess()
    started = time.monotonic()
    stop_event, cancelled_event, thread = start_heartbeat_thread("btk_0001", process, settings)
    try:
        thread.join(timeout=1)
        elapsed = time.monotonic() - started
        assert cancelled_event.is_set()
        assert process.terminated is True
        assert elapsed <= 1
    finally:
        stop_event.set()
        thread.join(timeout=1)


def test_heartbeat_thread_survives_transient_db_error(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    settings = _settings(tmp_path)
    old_heartbeat = utc_now() - timedelta(minutes=5)
    with Session(engine) as session:
        run = _run("btk_0001", status="running")
        run.heartbeat_at = old_heartbeat
        session.add(run)
        session.commit()

    calls = 0

    @contextmanager
    def flaky_session_scope(scoped_settings):
        nonlocal calls
        del scoped_settings
        calls += 1
        if calls == 1:
            raise OperationalError("select 1", {}, Exception("database is locked"))
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    monkeypatch.setattr("atlas20.api.worker.main.session_scope", flaky_session_scope)

    process = FakeProcess()
    stop_event, cancelled_event, thread = start_heartbeat_thread(
        "btk_0001",
        process,
        settings,
        heartbeat_interval_seconds=0.01,
    )
    time.sleep(0.05)
    stop_event.set()
    thread.join(timeout=1)

    with Session(engine) as session:
        updated = RunsRepo(session).get("btk_0001")
        assert calls >= 2
        assert updated is not None
        assert updated.heartbeat_at is not None
        assert updated.heartbeat_at > old_heartbeat
        assert not cancelled_event.is_set()


def test_timeout_kills_subprocess(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    settings = _settings(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", status="running"))
        session.commit()

    class TimeoutProcess(FakeProcess):
        def communicate(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired(cmd=["worker"], timeout=timeout)
            self.returncode = -9
            return b"", b""

    process = TimeoutProcess()
    monkeypatch.setattr("atlas20.api.worker.main.subprocess.Popen", lambda *args, **kwargs: process)

    _execute_run("btk_0001", settings, heartbeat_interval_seconds=0.01)

    with Session(engine) as session:
        failed = RunsRepo(session).get("btk_0001")
        assert failed is not None
        assert process.killed is True
        assert failed.status == "failed"
        assert failed.error == "timeout"


def test_completed_run_updates_status_and_metrics(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", status="running"))
        session.commit()

        updated = RunsRepo(session).update_metrics_from_completion(
            "btk_0001",
            return_pct=0.42,
            sharpe=1.9,
            max_dd=-0.18,
            duration_s=12,
        )

        assert updated is not None
        assert updated.status == "completed"
        assert updated.return_pct == 0.42
        assert updated.sharpe == 1.9
        assert updated.max_dd == -0.18
        assert updated.duration_s == 12
        assert updated.heartbeat_at is None


def test_update_metrics_respects_concurrent_cancel(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        run = _run("btk_0001", status="running")
        run.requested_cancel = True
        session.add(run)
        session.commit()

        updated = RunsRepo(session).update_metrics_from_completion(
            "btk_0001",
            return_pct=0.42,
            sharpe=1.9,
            max_dd=-0.18,
            duration_s=12,
        )

        assert updated is not None
        assert updated.status == "cancelled"
        assert "cancelled during execution" in str(updated.error)
        assert "completed" in str(updated.error)
        assert updated.requested_cancel is True


def test_failed_with_cancel_flag_becomes_cancelled(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        run = _run("btk_0001", status="running")
        run.requested_cancel = True
        session.add(run)
        session.commit()

        updated = RunsRepo(session).update_metrics_from_completion(
            "btk_0001",
            status="failed",
            error="pipeline crash",
            heartbeat_at=None,
            worker_pid=None,
        )

        assert updated is not None
        assert updated.status == "cancelled"
        assert "cancelled during execution" in str(updated.error)
        assert "pipeline crash" in str(updated.error)
        assert updated.requested_cancel is True


def test_failed_completion_after_accepted_cancel_uses_fresh_cancel_flag(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", status="running"))
        session.commit()

    stale_session = Session(engine)
    try:
        stale_repo = RunsRepo(stale_session)
        preloaded = stale_repo.get("btk_0001")
        assert preloaded is not None
        assert preloaded.requested_cancel is False

        with Session(engine) as cancel_session:
            RunsRepo(cancel_session).update("btk_0001", requested_cancel=True)
            cancel_session.commit()

        updated = stale_repo.update_metrics_from_completion(
            "btk_0001",
            status="failed",
            error="pipeline crash",
            heartbeat_at=None,
            worker_pid=None,
        )
        stale_session.commit()

        assert updated is not None
        assert updated.status == "cancelled"
        assert "would have been failed" in str(updated.error)
        assert "pipeline crash" in str(updated.error)
        assert updated.requested_cancel is True
    finally:
        stale_session.close()


def test_cancel_request_after_terminal_write_does_not_reopen_run(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", status="running"))
        session.commit()

    stale_cancel_session = Session(engine)
    try:
        stale_repo = RunsRepo(stale_cancel_session)
        preloaded = stale_repo.get("btk_0001")
        assert preloaded is not None
        assert preloaded.status == "running"

        with Session(engine) as terminal_session:
            RunsRepo(terminal_session).update_metrics_from_completion(
                "btk_0001",
                return_pct=0.42,
                sharpe=1.9,
                max_dd=-0.18,
                duration_s=12,
            )
            terminal_session.commit()

        updated = stale_repo.request_cancel("btk_0001")
        stale_cancel_session.commit()

        assert updated is not None
        assert updated.status == "completed"
        assert updated.requested_cancel is False
    finally:
        stale_cancel_session.close()


def test_cancel_queued_run_never_executes_subprocess(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    settings = _settings(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001"))
        session.commit()

        app = create_app()

        def override_get_session():
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

        app.dependency_overrides[get_session] = override_get_session
        response = TestClient(app).post("/api/runs/btk_0001/cancel")
        assert response.status_code == 202

    popen_calls = []

    class CompletedProcess(FakeProcess):
        def communicate(self, timeout=None):
            del timeout
            self.returncode = 0
            return b"", b""

    def fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return CompletedProcess()

    monkeypatch.setattr("atlas20.api.worker.main.subprocess.Popen", fake_popen)

    with Session(engine) as session:
        claimed = WorkerQueue(session).claim_one()
        if claimed is not None:
            _execute_run(claimed.run_id, settings, heartbeat_interval_seconds=0.01)

    with Session(engine) as session:
        cancelled = RunsRepo(session).get("btk_0001")
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert popen_calls == []


def test_execute_run_skips_subprocess_when_cancel_arrives_after_claim(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    settings = _settings(tmp_path)
    with Session(engine) as session:
        run = _run("btk_0001", status="running")
        run.requested_cancel = True
        session.add(run)
        session.commit()

    popen_calls = []

    class CompletedProcess(FakeProcess):
        def communicate(self, timeout=None):
            del timeout
            self.returncode = 0
            return b"", b""

    def fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return CompletedProcess()

    monkeypatch.setattr("atlas20.api.worker.main.subprocess.Popen", fake_popen)

    _execute_run("btk_0001", settings, heartbeat_interval_seconds=0.01)

    with Session(engine) as session:
        cancelled = RunsRepo(session).get("btk_0001")
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.error == "cancelled before execution"
        assert popen_calls == []


def test_failed_subprocess_marks_status_failed_with_error(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    settings = _settings(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", status="running"))
        session.commit()

    class FailedProcess(FakeProcess):
        def communicate(self, timeout=None):
            del timeout
            self.returncode = 1
            return b"stdout", b"boom"

    monkeypatch.setattr("atlas20.api.worker.main.subprocess.Popen", lambda *args, **kwargs: FailedProcess())

    _execute_run("btk_0001", settings, heartbeat_interval_seconds=0.01)

    with Session(engine) as session:
        failed = RunsRepo(session).get("btk_0001")
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error == "boom"


def test_recover_stale_runs_marks_failed(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", status="running", heartbeat_offset=-120))
        session.commit()

        recovered = recover_stale_runs(session, stale_after_seconds=60)

        failed = session.exec(select(Run).where(Run.run_id == "btk_0001")).one()
        assert recovered == 1
        assert failed.status == "failed"
        assert failed.error == "worker died - heartbeat stale"


def test_recover_stale_runs_ignores_fresh_heartbeats(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", status="running", heartbeat_offset=-10))
        session.commit()

        recovered = recover_stale_runs(session, stale_after_seconds=60)

        fresh = session.exec(select(Run).where(Run.run_id == "btk_0001")).one()
        assert recovered == 0
        assert fresh.status == "running"
