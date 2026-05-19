from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import subprocess
import time

from sqlmodel import SQLModel, Session, create_engine, select

from atlas20.api._time import utc_now
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
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
