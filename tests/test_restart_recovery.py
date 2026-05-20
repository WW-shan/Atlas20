from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from atlas20.api import app as app_module
from atlas20.api._time import utc_now
from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.settings import get_settings
from atlas20.api.worker.recovery import recover_stale_runs


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'recovery.sqlite').as_posix()}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _run(run_id: str, status: str, heartbeat_at=None) -> Run:
    return Run(
        run_id=run_id,
        strategy="ATLAS Adaptive v3",
        strategy_family="ATLAS",
        universe="Top-20",
        window_start=date(2024, 1, 1),
        window_end=date(2026, 5, 18),
        status=status,
        heartbeat_at=heartbeat_at,
    )


def test_stale_running_without_heartbeat_recovers_to_failed(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", "running", None))
        session.commit()

        recovered = recover_stale_runs(session, stale_after_seconds=60)

        run = RunsRepo(session).get("btk_0001")
        assert recovered == 1
        assert run is not None
        assert run.status == "failed"


def test_fresh_running_heartbeat_is_untouched(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", "running", utc_now() - timedelta(seconds=10)))
        session.commit()

        recovered = recover_stale_runs(session, stale_after_seconds=60)

        run = RunsRepo(session).get("btk_0001")
        assert recovered == 0
        assert run is not None
        assert run.status == "running"


def test_queued_runs_are_untouched_by_recovery(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", "queued", None))
        session.commit()

        recovered = recover_stale_runs(session, stale_after_seconds=60)

        run = RunsRepo(session).get("btk_0001")
        assert recovered == 0
        assert run is not None
        assert run.status == "queued"


def test_multiple_stale_runs_are_recovered(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        session.add(_run("btk_0001", "running", None))
        session.add(_run("btk_0002", "running", utc_now() - timedelta(seconds=120)))
        session.commit()

        recovered = recover_stale_runs(session, stale_after_seconds=60)

        assert recovered == 2
        assert RunsRepo(session).get("btk_0001").status == "failed"
        assert RunsRepo(session).get("btk_0002").status == "failed"


def test_worker_startup_recovery_skips_other_workers_runs(tmp_path):
    from atlas20.api.worker.recovery import recover_runs_owned_by_pid

    engine = _engine(tmp_path)
    with Session(engine) as session:
        mine = _run("btk_0001", "running", None)
        mine.worker_pid = 111
        other = _run("btk_0002", "running", None)
        other.worker_pid = 222
        session.add(mine)
        session.add(other)
        session.commit()

        recovered = recover_runs_owned_by_pid(session, my_pid=111)

        mine_after = RunsRepo(session).get("btk_0001")
        other_after = RunsRepo(session).get("btk_0002")
        assert recovered == 1
        assert mine_after is not None
        assert mine_after.status == "failed"
        assert mine_after.error == "worker died — restart recovery"
        assert other_after is not None
        assert other_after.status == "running"


def test_lifespan_calls_recover_stale_runs(tmp_path, monkeypatch):
    db_path = tmp_path / "atlas20.sqlite"
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    calls = []

    def fake_recover(session, stale_after_seconds):
        calls.append((session is not None, stale_after_seconds))
        return 0

    monkeypatch.setattr(app_module, "recover_stale_runs", fake_recover)

    try:
        with TestClient(create_app()):
            pass
    finally:
        get_settings.cache_clear()

    assert calls == [(True, 60)]
