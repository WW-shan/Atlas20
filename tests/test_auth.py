import re

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.dependencies.auth import verify_api_key
from atlas20.api.repositories import get_session
from atlas20.api.settings import get_settings


DEFAULT_BACKTEST_CONFIG = {
    "preset": "ATLAS Adaptive v3",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}

REPORT_REQUEST = {
    "type": "compare",
    "formats": ["markdown"],
    "strategy": "ATLAS Adaptive v3",
}

MUTATING_CASES = [
    ("/api/backtests/run", DEFAULT_BACKTEST_CONFIG, 200),
    ("/api/runs/btk_0142/favorite", None, 200),
    ("/api/runs/btk_0148/cancel", None, 202),
    ("/api/universe/refresh", None, 202),
    ("/api/reports/generate", REPORT_REQUEST, 202),
]


def _error_message(response) -> str:
    return response.json()["error"]["message"]


def _client(tmp_path, monkeypatch, db_session: Session, *, api_keys: str | None = None) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'auth.sqlite').as_posix()}")
    if api_keys is None:
        monkeypatch.delenv("ATLAS20_API_KEYS", raising=False)
    else:
        monkeypatch.setenv("ATLAS20_API_KEYS", api_keys)
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def test_no_api_keys_configured_leaves_mutating_routes_backward_compatible(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)

    for path, payload, expected_status in MUTATING_CASES:
        response = client.post(path, json=payload) if payload is not None else client.post(path)
        assert response.status_code == expected_status


@pytest.mark.parametrize(("path", "payload", "expected_status"), MUTATING_CASES)
def test_valid_api_key_allows_each_mutating_route(
    tmp_path,
    monkeypatch,
    db_session: Session,
    path: str,
    payload: dict | None,
    expected_status: int,
):
    client = _client(tmp_path, monkeypatch, db_session, api_keys="valid-key")

    response = client.post(path, json=payload, headers={"X-API-Key": "valid-key"}) if payload is not None else client.post(
        path,
        headers={"X-API-Key": "valid-key"},
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize(("path", "payload", "_expected_status"), MUTATING_CASES)
def test_missing_api_key_rejects_each_mutating_route(
    tmp_path,
    monkeypatch,
    db_session: Session,
    path: str,
    payload: dict | None,
    _expected_status: int,
):
    client = _client(tmp_path, monkeypatch, db_session, api_keys="valid-key")

    response = client.post(path, json=payload) if payload is not None else client.post(path)

    assert response.status_code == 401
    assert _error_message(response) == "X-API-Key header required"


def test_api_key_required_for_mutating_routes_when_configured(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session, api_keys="valid-key")

    missing = client.post("/api/reports/generate", json=REPORT_REQUEST)
    invalid = client.post("/api/reports/generate", json=REPORT_REQUEST, headers={"X-API-Key": "wrong-key"})
    valid = client.post("/api/reports/generate", json=REPORT_REQUEST, headers={"X-API-Key": "valid-key"})

    assert missing.status_code == 401
    assert _error_message(missing) == "X-API-Key header required"
    assert invalid.status_code == 401
    assert _error_message(invalid) == "invalid API key"
    assert valid.status_code == 202


def test_get_routes_remain_unauthenticated_when_api_keys_are_configured(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session, api_keys="valid-key")

    response = client.get("/api/reports")

    assert response.status_code == 200


def test_verify_api_key_returns_non_secret_principal(monkeypatch):
    raw_key = "valid-secret-key"
    monkeypatch.setenv("ATLAS20_API_KEYS", raw_key)
    get_settings.cache_clear()

    principal = verify_api_key(raw_key)

    assert re.fullmatch(r"client-[0-9a-f]{8}", principal)
    assert raw_key not in principal
