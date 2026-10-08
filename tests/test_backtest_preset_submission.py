"""POST /api/backtests/run rejects presets the engine does not know, at submission."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.repositories import RunsRepo, get_session
from atlas20.api.settings import get_settings


def _config(preset: str) -> dict:
    return {
        "preset": preset,
        "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
        "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
        "allocation": {"positionPct": 5.0, "slots": 10},
        "costs": {"feeBps": 10, "slippageBps": 5},
    }


@pytest.fixture
def client(tmp_path, monkeypatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'presets.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


@pytest.mark.parametrize(
    ("preset", "message"),
    [("ATLAS Adaptive v3", "unknown preset"), ("universe_refresh", "reserved for internal runs")],
)
def test_unknown_or_internal_preset_is_rejected_before_a_run_is_queued(
    client: TestClient, db_session: Session, preset: str, message: str
) -> None:
    queued_before = len(RunsRepo(db_session).list_queue())

    response = client.post("/api/backtests/run", json=_config(preset))

    assert response.status_code == 422
    assert message in response.json()["error"]["message"]
    assert len(RunsRepo(db_session).list_queue()) == queued_before


def test_known_preset_is_queued(client: TestClient) -> None:
    response = client.post("/api/backtests/run", json=_config("base"))

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
