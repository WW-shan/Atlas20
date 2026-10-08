"""Once a run reaches a terminal status nothing may move it to another one."""

from __future__ import annotations

from datetime import date, timedelta
import subprocess

import pytest
from sqlalchemy import event
from sqlmodel import SQLModel, Session, create_engine

from atlas20.api._time import utc_now
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.settings import Settings
from atlas20.api.worker import main as worker_main
from atlas20.api.worker.recovery import recover_stale_runs


def _setup(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'terminal.sqlite').as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    settings = Settings(
        db_url=db_url,
        report_root=tmp_path / "reports",
        project_root=tmp_path,
        run_timeout_seconds=1,
        worker_poll_interval_seconds=0.01,
    )
    return engine, settings


def _add(engine, status: str, *, run_id: str = "btk_0001", heartbeat_age_s: float | None = None, **fields) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                run_id=run_id,
                strategy="base",
                universe="Top-5",
                window_start=date(2026, 1, 1),
                window_end=date(2026, 2, 1),
                status=status,
                started_at=utc_now() - timedelta(minutes=5),
                heartbeat_at=None if heartbeat_age_s is None else utc_now() - timedelta(seconds=heartbeat_age_s),
                **fields,
            )
        )
        session.commit()


def _get(engine, run_id: str = "btk_0001") -> Run:
    with Session(engine) as session:
        run = RunsRepo(session).get(run_id)
        assert run is not None
        return run


def test_late_completion_does_not_reopen_a_run_failed_by_recovery(tmp_path) -> None:
    engine, _ = _setup(tmp_path)
    _add(engine, "running", heartbeat_age_s=120)
    with Session(engine) as session:
        assert recover_stale_runs(session, stale_after_seconds=60) == 1
        session.commit()

    with Session(engine) as session:
        updated = RunsRepo(session).update_metrics_from_completion(
            "btk_0001", return_pct=0.1, sharpe=1.0, max_dd=-0.1, duration_s=10
        )
        session.commit()

    assert updated is None
    assert _get(engine).status == "failed"
    assert _get(engine).return_pct is None


@pytest.mark.parametrize("terminal", ["completed", "failed", "cancelled"])
def test_timeout_failure_does_not_overwrite_a_finished_run(tmp_path, terminal) -> None:
    engine, settings = _setup(tmp_path)
    _add(engine, terminal, duration_s=10, error=None if terminal == "completed" else "earlier")

    worker_main._mark_failed("btk_0001", settings, "timeout")

    run = _get(engine)
    assert run.status == terminal
    assert run.error != "timeout"


@pytest.mark.parametrize("terminal", ["completed", "failed"])
def test_late_cancel_does_not_overwrite_a_finished_run(tmp_path, terminal) -> None:
    engine, settings = _setup(tmp_path)
    _add(engine, terminal, duration_s=10)

    worker_main._mark_cancelled("btk_0001", settings)

    assert _get(engine).status == terminal


def test_subprocess_timeout_after_the_run_completed_keeps_it_completed(tmp_path, monkeypatch) -> None:
    engine, settings = _setup(tmp_path)
    _add(engine, "running", heartbeat_age_s=0)

    class CompletesThenHangs:
        returncode: int | None = None

        def communicate(self, timeout=None):
            if timeout is not None:
                # run_one committed "completed", then report generation ran past the timeout.
                with Session(engine) as session:
                    RunsRepo(session).update_metrics_from_completion(
                        "btk_0001", return_pct=0.2, sharpe=1.1, max_dd=-0.1, duration_s=1
                    )
                    session.commit()
                raise subprocess.TimeoutExpired(cmd=["run_one"], timeout=timeout)
            self.returncode = -9
            return b"", b""

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def terminate(self):
            self.returncode = -15

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(worker_main.subprocess, "Popen", lambda *args, **kwargs: CompletesThenHangs())

    worker_main._execute_run("btk_0001", settings, heartbeat_interval_seconds=0.01)

    run = _get(engine)
    assert run.status == "completed"
    assert run.return_pct == 0.2


def test_stale_recovery_does_not_touch_a_run_that_finished_meanwhile(tmp_path) -> None:
    engine, settings = _setup(tmp_path)
    _add(engine, "running", heartbeat_age_s=120)
    fired = False

    def complete_before_recovery_writes(conn, cursor, statement, parameters, context, executemany):
        nonlocal fired
        if fired or not statement.lstrip().upper().startswith("UPDATE RUNS"):
            return
        fired = True
        # The run finishes on another connection after recovery selected it as stale.
        other = create_engine(settings.db_url)
        try:
            with Session(other) as session:
                RunsRepo(session).update_metrics_from_completion(
                    "btk_0001", return_pct=0.3, sharpe=1.2, max_dd=-0.1, duration_s=5
                )
                session.commit()
        finally:
            other.dispose()

    event.listen(engine, "before_cursor_execute", complete_before_recovery_writes)
    try:
        with Session(engine) as session:
            recovered = recover_stale_runs(session, stale_after_seconds=60)
            session.commit()
    finally:
        event.remove(engine, "before_cursor_execute", complete_before_recovery_writes)

    assert fired
    assert recovered == 0
    assert _get(engine).status == "completed"
