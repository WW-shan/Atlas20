from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.repositories import get_session
from atlas20.api.settings import get_settings


DEFAULT_BACKTEST_CONFIG = {
    "preset": "ATLAS Adaptive v3",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}


@pytest.fixture
def client(tmp_path, monkeypatch, db_session: Session) -> Iterator[TestClient]:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'errors.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client


def assert_error_envelope(
    response,
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> dict[str, object]:
    assert response.status_code == status_code
    assert response.headers["X-Request-ID"] == request_id
    payload = response.json()
    assert set(payload) == {"error"}
    error = payload["error"]
    assert error["code"] == code
    assert error["message"] == message
    assert error["request_id"] == request_id
    assert "details" in error
    return error


def test_http_exception_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/runs/btk_999999", headers={"X-Request-ID": "req-http-404"})

    error = assert_error_envelope(
        response,
        status_code=404,
        code="not_found",
        message="run not found",
        request_id="req-http-404",
    )
    assert error["details"] is None


def test_manual_validation_exception_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/runs?view=list", headers={"X-Request-ID": "req-manual-422"})

    error = assert_error_envelope(
        response,
        status_code=422,
        code="validation_error",
        message="unknown query parameter(s): view",
        request_id="req-manual-422",
    )
    assert error["details"] is None


def test_request_validation_exception_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/runs?page=0", headers={"X-Request-ID": "req-schema-422"})

    error = assert_error_envelope(
        response,
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        request_id="req-schema-422",
    )
    assert isinstance(error["details"], list)
    assert error["details"][0]["loc"] == ["query", "page"]


def test_rate_limit_exception_uses_error_envelope(tmp_path, monkeypatch, db_session: Session) -> None:
    api_key = f"errors-{uuid4().hex}"
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'errors-rate.sqlite').as_posix()}")
    monkeypatch.setenv("ATLAS20_API_KEYS", api_key)
    get_settings.cache_clear()
    app = create_app()

    def override_get_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        headers = {"X-API-Key": api_key, "X-Request-ID": "req-rate-429"}
        for _ in range(10):
            assert test_client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers).status_code == 200
        response = test_client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)

    error = assert_error_envelope(
        response,
        status_code=429,
        code="rate_limited",
        message="Rate limit exceeded",
        request_id="req-rate-429",
    )
    assert error["details"] is not None
    assert int(response.headers["Retry-After"]) >= 0
