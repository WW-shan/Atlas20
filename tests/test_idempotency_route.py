from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import atlas20.api.repositories.idempotency_repo as idempotency_repo_module
from atlas20.api.app import create_app
from atlas20.api.repositories import IdempotencyRepo, RunsRepo, get_session
from atlas20.api.settings import get_settings


DEFAULT_BACKTEST_CONFIG = {
    "preset": "ATLAS Adaptive v3",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}


@pytest.fixture
def client(tmp_path, monkeypatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'atlas20.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def test_post_backtest_without_idempotency_header_creates_run(client: TestClient, db_session: Session):
    response = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG)

    assert response.status_code == 200
    assert response.json()["run_id"] == "btk_0149"
    assert len(RunsRepo(db_session).list_queue()) == 3


def test_post_backtest_with_same_idempotency_key_returns_cached_response(client: TestClient, db_session: Session):
    headers = {"Idempotency-Key": "abc123"}

    first = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)
    second = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(RunsRepo(db_session).list_queue()) == 3


def test_post_backtest_accepts_64_char_idempotency_key(client: TestClient):
    response = client.post(
        "/api/backtests/run",
        json=DEFAULT_BACKTEST_CONFIG,
        headers={"Idempotency-Key": "a" * 64},
    )

    assert response.status_code == 200


def test_post_backtest_rejects_65_char_idempotency_key(client: TestClient):
    response = client.post(
        "/api/backtests/run",
        json=DEFAULT_BACKTEST_CONFIG,
        headers={"Idempotency-Key": "a" * 65},
    )

    assert response.status_code == 422


def test_post_backtest_rejects_special_character_idempotency_key(client: TestClient):
    response = client.post(
        "/api/backtests/run",
        json=DEFAULT_BACKTEST_CONFIG,
        headers={"Idempotency-Key": "!!!"},
    )

    assert response.status_code == 422


def test_post_backtest_expired_idempotency_key_executes_again(client: TestClient, db_session: Session, monkeypatch):
    headers = {"Idempotency-Key": "abc123"}
    first = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)
    row = IdempotencyRepo(db_session).get("abc123")
    assert row is not None
    monkeypatch.setattr(idempotency_repo_module._time, "utc_now", lambda: row.expires_at + timedelta(hours=1))

    second = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["run_id"] != first.json()["run_id"]
    assert len(RunsRepo(db_session).list_queue()) == 4
