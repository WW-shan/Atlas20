import base64
import hashlib
import hmac
import json
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


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt(payload: dict[str, object], secret: str = "jwt-secret") -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(secret.encode(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def _error_message(response) -> str:
    return response.json()["error"]["message"]


def _client(
    tmp_path,
    monkeypatch,
    db_session: Session,
    *,
    api_keys: str | None = None,
    jwt_auth_enabled: bool = False,
    jwt_secret_key: str | None = None,
    jwt_issuer: str | None = None,
    jwt_audience: str | None = None,
) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'auth.sqlite').as_posix()}")
    if api_keys is None:
        monkeypatch.delenv("ATLAS20_API_KEYS", raising=False)
    else:
        monkeypatch.setenv("ATLAS20_API_KEYS", api_keys)
    if jwt_auth_enabled:
        monkeypatch.setenv("ATLAS20_JWT_AUTH_ENABLED", "true")
    else:
        monkeypatch.delenv("ATLAS20_JWT_AUTH_ENABLED", raising=False)
    if jwt_secret_key is None:
        monkeypatch.delenv("ATLAS20_JWT_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("ATLAS20_JWT_SECRET_KEY", jwt_secret_key)
    if jwt_issuer is None:
        monkeypatch.delenv("ATLAS20_JWT_ISSUER", raising=False)
    else:
        monkeypatch.setenv("ATLAS20_JWT_ISSUER", jwt_issuer)
    if jwt_audience is None:
        monkeypatch.delenv("ATLAS20_JWT_AUDIENCE", raising=False)
    else:
        monkeypatch.setenv("ATLAS20_JWT_AUDIENCE", jwt_audience)
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


def test_valid_bearer_token_allows_mutating_route(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session, jwt_auth_enabled=True, jwt_secret_key="jwt-secret")
    token = _jwt({"sub": "researcher", "exp": 4_102_444_800})

    response = client.post(
        "/api/reports/generate",
        json=REPORT_REQUEST,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 202


def test_missing_bearer_rejected_when_jwt_auth_enabled(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session, jwt_auth_enabled=True, jwt_secret_key="jwt-secret")

    response = client.post("/api/reports/generate", json=REPORT_REQUEST)

    assert response.status_code == 401
    assert _error_message(response) == "Bearer token required"


def test_invalid_bearer_token_rejected(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session, jwt_auth_enabled=True, jwt_secret_key="jwt-secret")
    token = _jwt({"sub": "researcher", "exp": 4_102_444_800}, secret="wrong-secret")

    response = client.post(
        "/api/reports/generate",
        json=REPORT_REQUEST,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert _error_message(response) == "invalid bearer token"


def test_jwt_issuer_and_audience_claims_are_enforced(tmp_path, monkeypatch, db_session: Session):
    client = _client(
        tmp_path,
        monkeypatch,
        db_session,
        jwt_auth_enabled=True,
        jwt_secret_key="jwt-secret",
        jwt_issuer="https://auth.example.com",
        jwt_audience="atlas20-api",
    )
    valid = _jwt(
        {
            "sub": "researcher",
            "exp": 4_102_444_800,
            "iss": "https://auth.example.com",
            "aud": ["atlas20-api", "atlas20-console"],
        }
    )
    wrong_audience = _jwt(
        {
            "sub": "researcher",
            "exp": 4_102_444_800,
            "iss": "https://auth.example.com",
            "aud": "other-service",
        }
    )

    allowed = client.post("/api/reports/generate", json=REPORT_REQUEST, headers={"Authorization": f"Bearer {valid}"})
    rejected = client.post(
        "/api/reports/generate",
        json=REPORT_REQUEST,
        headers={"Authorization": f"Bearer {wrong_audience}"},
    )

    assert allowed.status_code == 202
    assert rejected.status_code == 401
    assert _error_message(rejected) == "invalid bearer token"


def test_api_key_still_allows_when_jwt_auth_enabled(tmp_path, monkeypatch, db_session: Session):
    client = _client(
        tmp_path,
        monkeypatch,
        db_session,
        api_keys="valid-key",
        jwt_auth_enabled=True,
        jwt_secret_key="jwt-secret",
    )

    response = client.post("/api/reports/generate", json=REPORT_REQUEST, headers={"X-API-Key": "valid-key"})

    assert response.status_code == 202


def test_verify_api_key_returns_non_secret_jwt_principal(monkeypatch):
    monkeypatch.setenv("ATLAS20_JWT_AUTH_ENABLED", "true")
    monkeypatch.setenv("ATLAS20_JWT_SECRET_KEY", "jwt-secret")
    get_settings.cache_clear()
    token = _jwt({"sub": "researcher@example.com", "exp": 4_102_444_800})

    principal = verify_api_key(authorization=f"Bearer {token}")

    assert re.fullmatch(r"jwt-[0-9a-f]{8}", principal)
    assert "researcher" not in principal
