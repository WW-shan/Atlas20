from copy import deepcopy
from datetime import timedelta
import threading

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import atlas20.api.repositories.idempotency_repo as idempotency_repo_module
from atlas20.api.app import create_app
from atlas20.api.db.models import IdempotencyKey
from atlas20.api.repositories import IdempotencyRepo, RunsRepo, get_session
from atlas20.api.schemas import BacktestConfig
from atlas20.api.services import get_console_service
from atlas20.api.settings import get_settings


DEFAULT_BACKTEST_CONFIG = {
    "preset": "base",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}


@pytest.fixture
def client(tmp_path, monkeypatch, db_session: Session) -> TestClient:
    return _client_for(tmp_path, monkeypatch, db_session)


def _client_for(tmp_path, monkeypatch, db_session: Session) -> TestClient:
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


def _other_config() -> dict:
    changed = deepcopy(DEFAULT_BACKTEST_CONFIG)
    changed["universe"]["topN"] = 10
    return changed


def test_post_backtest_reused_idempotency_key_with_different_body_is_rejected(client: TestClient, db_session: Session):
    headers = {"Idempotency-Key": "abc123"}
    first = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)

    second = client.post("/api/backtests/run", json=_other_config(), headers=headers)

    assert first.status_code == 200
    assert second.status_code == 422
    assert "Idempotency-Key" in second.json()["error"]["message"]
    assert len(RunsRepo(db_session).list_queue()) == 3


def test_post_backtest_same_key_from_another_principal_is_rejected(tmp_path, monkeypatch, db_session: Session):
    monkeypatch.setenv("ATLAS20_API_KEYS", "key-one,key-two")
    app_client = _client_for(tmp_path, monkeypatch, db_session)
    first = app_client.post(
        "/api/backtests/run",
        json=DEFAULT_BACKTEST_CONFIG,
        headers={"Idempotency-Key": "shared", "X-API-Key": "key-one"},
    )

    second = app_client.post(
        "/api/backtests/run",
        json=DEFAULT_BACKTEST_CONFIG,
        headers={"Idempotency-Key": "shared", "X-API-Key": "key-two"},
    )

    assert first.status_code == 200
    assert second.status_code == 422
    assert "run_id" not in second.text


def test_post_backtest_same_key_while_first_request_is_in_flight_returns_409(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'race.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()
    real_service = get_console_service()
    entered = threading.Event()
    release = threading.Event()

    class BlockingService:
        def __getattr__(self, name):
            return getattr(real_service, name)

        def register_new_backtest(self, session, config):
            entered.set()
            assert release.wait(timeout=10)
            return real_service.register_new_backtest(session, config)

    app.dependency_overrides[get_console_service] = BlockingService
    headers = {"Idempotency-Key": "same-key"}
    results: dict[str, object] = {}

    with TestClient(app) as race_client:
        first = threading.Thread(
            target=lambda: results.update(first=race_client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers))
        )
        first.start()
        assert entered.wait(timeout=10)
        second = race_client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)
        release.set()
        first.join(timeout=10)
        replay = race_client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)
        runs = race_client.get("/api/runs", params={"dateRange": "all"}).json()

    first_response = results["first"]
    assert first_response.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["message"] == "a request with this Idempotency-Key is still in progress"
    assert replay.status_code == 200
    assert replay.json() == first_response.json()
    assert runs["total"] == 1


def test_post_backtest_failed_request_releases_idempotency_key(client: TestClient, db_session: Session):
    real_service = get_console_service()
    calls = {"count": 0}

    class FlakyService:
        def __getattr__(self, name):
            return getattr(real_service, name)

        def register_new_backtest(self, session, config):
            calls["count"] += 1
            if calls["count"] == 1:
                raise ValueError("preset rejected")
            return real_service.register_new_backtest(session, config)

    client.app.dependency_overrides[get_console_service] = FlakyService
    headers = {"Idempotency-Key": "retry-me"}

    rejected = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)
    retried = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)

    assert rejected.status_code == 422
    assert retried.status_code == 200
    assert retried.json()["run_id"] == "btk_0149"


def test_idempotency_claim_expires_when_the_claiming_request_never_finished(client: TestClient, db_session: Session, monkeypatch):
    fingerprint = idempotency_repo_module.request_fingerprint(
        principal="anonymous",
        method="POST",
        path="/api/backtests/run",
        body=BacktestConfig.model_validate(DEFAULT_BACKTEST_CONFIG).model_dump(mode="json"),
    )
    claim = IdempotencyRepo(db_session).claim("orphaned", method="POST", path="/api/backtests/run", request_hash=fingerprint)
    db_session.commit()
    assert claim.status == "claimed"
    blocked = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers={"Idempotency-Key": "orphaned"})
    row = db_session.get(IdempotencyKey, "orphaned")
    assert row is not None
    monkeypatch.setattr(idempotency_repo_module._time, "utc_now", lambda: row.expires_at + timedelta(seconds=1))

    retried = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers={"Idempotency-Key": "orphaned"})

    assert blocked.status_code == 409
    assert retried.status_code == 200
