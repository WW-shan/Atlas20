"""Write routes must commit before the response is sent to the client."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, create_engine, select

from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.repositories import _session as session_module
from atlas20.api.settings import get_settings


BACKTEST_CONFIG = {
    "preset": "base",
    "universe": {"topN": 5, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2026-01-01", "end": "2026-02-01", "rebalance": "Weekly"},
    "allocation": {"positionPct": 25.0, "slots": 3},
    "costs": {"feeBps": 1.0, "slippageBps": 1.0},
}


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    (tmp_path / "reports").mkdir()
    (tmp_path / "data").mkdir()
    db_url = f"sqlite:///{(tmp_path / 'commit.sqlite').as_posix()}"
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setenv("ATLAS20_DB_URL", db_url)
    get_settings.cache_clear()
    return db_url


def _seed_running_run(db_url: str, run_id: str = "btk_0001") -> None:
    engine = create_engine(db_url)
    try:
        with Session(engine) as session:
            session.add(
                Run(
                    run_id=run_id,
                    strategy="base",
                    universe="Top-5",
                    window_start=date(2026, 1, 1),
                    window_end=date(2026, 2, 1),
                    status="running",
                )
            )
            session.commit()
    finally:
        engine.dispose()


def _committed_run(db_url: str, run_id: str) -> Run | None:
    engine = create_engine(db_url)
    try:
        with Session(engine) as session:
            return session.exec(select(Run).where(Run.run_id == run_id)).first()
    finally:
        engine.dispose()


WRITE_ROUTES = [
    ("POST", "/api/backtests/run", BACKTEST_CONFIG),
    ("POST", "/api/runs/btk_0001/favorite", None),
    ("POST", "/api/runs/btk_0001/cancel", None),
]


@pytest.mark.parametrize(("method", "path", "body"), WRITE_ROUTES)
def test_write_is_committed_before_the_response_starts(tmp_path, monkeypatch, method, path, body) -> None:
    db_url = _configure(tmp_path, monkeypatch)
    app = create_app()
    observed: dict[str, Any] = {}

    async def observing_app(scope, receive, send):
        async def observing_send(message):
            if scope["type"] == "http" and message["type"] == "http.response.start":
                observed["run"] = _committed_run(db_url, "btk_0001")
                observed["latest"] = _committed_run(db_url, "btk_0002")
            await send(message)

        await app(scope, receive, observing_send)

    with TestClient(observing_app) as client:
        _seed_running_run(db_url)
        response = client.request(method, path, json=body)

    assert response.status_code in {200, 202}, response.text
    if path == "/api/backtests/run":
        assert response.json()["run_id"] == "btk_0002"
        assert observed["latest"] is not None, "run was not committed when the response started"
    elif path.endswith("/favorite"):
        assert observed["run"].favorited is True, "favorite toggle was not committed when the response started"
    else:
        assert observed["run"].requested_cancel is True, "cancel request was not committed when the response started"


def test_commit_failure_is_reported_instead_of_a_phantom_run(tmp_path, monkeypatch) -> None:
    db_url = _configure(tmp_path, monkeypatch)
    app = create_app()

    class FailingCommitSession(Session):
        def commit(self) -> None:
            raise OperationalError("COMMIT", {}, Exception("database is locked"))

    with TestClient(app, raise_server_exceptions=False) as client:
        monkeypatch.setattr(session_module, "Session", FailingCommitSession)
        response = client.post("/api/backtests/run", json=BACKTEST_CONFIG)
        monkeypatch.setattr(session_module, "Session", Session)

    assert response.status_code == 500, response.text
    assert _committed_run(db_url, "btk_0001") is None
