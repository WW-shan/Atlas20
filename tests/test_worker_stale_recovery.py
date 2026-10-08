"""Workers recover runs orphaned by any dead worker, without trusting PIDs or cross-host clocks."""

from __future__ import annotations

from datetime import date, timedelta
import os
import threading
import time

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from atlas20.api._time import utc_now
from atlas20.api.app import create_app
from atlas20.api.db.migrate import upgrade_to_head
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.settings import Settings, get_settings
from atlas20.api.worker import main as worker_main
from atlas20.api.worker import recovery


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _db(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'stale.sqlite').as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return db_url, engine


def _add_running(engine, run_id: str = "btk_0001", *, heartbeat_age_s: float | None = 5.0, **fields) -> None:
    heartbeat_at = None if heartbeat_age_s is None else utc_now() - timedelta(seconds=heartbeat_age_s)
    with Session(engine) as session:
        session.add(
            Run(
                run_id=run_id,
                strategy="base",
                universe="Top-5",
                window_start=date(2026, 1, 1),
                window_end=date(2026, 2, 1),
                status="running",
                started_at=utc_now() - timedelta(minutes=5),
                heartbeat_at=heartbeat_at,
                **fields,
            )
        )
        session.commit()


def _beat(engine, run_id: str = "btk_0001", *, age_s: float) -> None:
    with Session(engine) as session:
        RunsRepo(session).update(run_id, heartbeat_at=utc_now() - timedelta(seconds=age_s))
        session.commit()


def _status(engine, run_id: str = "btk_0001") -> tuple[str, str | None]:
    with Session(engine) as session:
        run = RunsRepo(session).get(run_id)
        assert run is not None
        return run.status, run.error


def test_stale_threshold_is_derived_from_the_heartbeat_interval() -> None:
    assert recovery.stale_threshold_seconds(2.0) == 60.0
    assert recovery.stale_threshold_seconds(10.0) == 150.0


def test_monitor_recovers_a_run_once_its_heartbeat_stops_advancing(tmp_path) -> None:
    _, engine = _db(tmp_path)
    _add_running(engine)
    clock = FakeClock()
    monitor = recovery.StaleRunMonitor(60.0, clock=clock)

    with Session(engine) as session:
        assert monitor.recover(session) == 0
        session.commit()
    clock.now += 59.0
    with Session(engine) as session:
        assert monitor.recover(session) == 0
        session.commit()
    assert _status(engine) == ("running", None)

    clock.now += 1.0
    with Session(engine) as session:
        assert monitor.recover(session) == 1
        session.commit()

    assert _status(engine) == ("failed", recovery.STALE_HEARTBEAT_ERROR)


def test_monitor_keeps_a_live_run_whose_worker_clock_is_behind(tmp_path) -> None:
    _, engine = _db(tmp_path)
    # The owning worker's clock runs ten minutes behind this host, so its
    # heartbeats look ancient here even though they keep advancing.
    _add_running(engine, heartbeat_age_s=600)
    clock = FakeClock()
    monitor = recovery.StaleRunMonitor(60.0, clock=clock)

    for step in range(1, 6):
        with Session(engine) as session:
            assert monitor.recover(session) == 0
            session.commit()
        clock.now += 30.0
        _beat(engine, age_s=600 - step * 30)

    assert _status(engine) == ("running", None)


def test_monitor_finishes_a_cancel_requested_orphan_as_cancelled(tmp_path) -> None:
    _, engine = _db(tmp_path)
    _add_running(engine, requested_cancel=True)
    clock = FakeClock()
    monitor = recovery.StaleRunMonitor(60.0, clock=clock)

    with Session(engine) as session:
        monitor.recover(session)
        session.commit()
    clock.now += 60.0
    with Session(engine) as session:
        assert monitor.recover(session) == 1
        session.commit()

    status, error = _status(engine)
    assert status == "cancelled"
    assert "cancelled during execution" in str(error)


def test_recovery_thread_recovers_orphans_while_the_main_loop_is_busy(tmp_path) -> None:
    db_url, engine = _db(tmp_path)
    _add_running(engine)
    settings = Settings(db_url=db_url, report_root=tmp_path / "reports", worker_heartbeat_interval_seconds=0.01)
    stop = threading.Event()
    monitor = recovery.StaleRunMonitor(0.05)

    thread = worker_main.start_recovery_thread(settings, monitor, stop)
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _status(engine)[0] == "running":
            time.sleep(0.02)
    finally:
        stop.set()
        thread.join(timeout=2)

    assert _status(engine) == ("failed", recovery.STALE_HEARTBEAT_ERROR)
    assert not thread.is_alive()


def test_worker_startup_leaves_a_live_run_with_the_same_pid_alone(tmp_path, monkeypatch) -> None:
    # Every containerised worker is PID 1: a restarting replica must not
    # treat another replica's live run as its own dead one.
    db_url, engine = _db(tmp_path)
    _add_running(engine, heartbeat_age_s=1, worker_pid=os.getpid())
    monkeypatch.setenv("ATLAS20_DB_URL", db_url)
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    get_settings.cache_clear()
    monkeypatch.setattr(worker_main, "start_metrics_server", lambda port: None)
    monkeypatch.setattr(worker_main, "setup_signal_handlers", lambda: None)
    monkeypatch.setattr(worker_main, "_shutdown_requested", threading.Event())
    worker_main._shutdown_requested.set()

    worker_main.main()

    assert _status(engine) == ("running", None)


def test_worker_ids_are_unique_and_name_the_host_and_process() -> None:
    first = worker_main.make_worker_id()
    second = worker_main.make_worker_id()

    assert first != second
    assert f":{os.getpid()}:" in first


def test_api_startup_does_not_fail_runs_by_comparing_clocks(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{(tmp_path / 'api.sqlite').as_posix()}"
    monkeypatch.setenv("ATLAS20_DB_URL", db_url)
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    upgrade_to_head(get_settings())
    engine = create_engine(db_url)
    # Five minutes old by this host's clock; the API cannot tell whether the
    # owning worker is dead or just runs on a host whose clock is behind.
    _add_running(engine, heartbeat_age_s=300)

    with TestClient(create_app()):
        pass

    assert _status(engine) == ("running", None)
