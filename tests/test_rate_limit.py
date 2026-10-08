import base64
import hashlib
import hmac
import json
import logging
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.repositories import get_session
from atlas20.api.settings import get_settings


DEFAULT_BACKTEST_CONFIG = {
    "preset": "base",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}


def _client(tmp_path, monkeypatch, db_session: Session, api_keys: list[str]) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'rate.sqlite').as_posix()}")
    monkeypatch.setenv("ATLAS20_API_KEYS", ",".join(api_keys))
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def test_backtest_run_rate_limit_returns_429_on_eleventh_post(tmp_path, monkeypatch, db_session: Session):
    key = f"backtest-{uuid4().hex}"
    client = _client(tmp_path, monkeypatch, db_session, [key])

    headers = {"X-API-Key": key}
    statuses = [
        client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers).status_code for _ in range(11)
    ]

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


def test_rate_limit_429_includes_retry_after_header(tmp_path, monkeypatch, db_session: Session):
    key = f"retry-after-{uuid4().hex}"
    client = _client(tmp_path, monkeypatch, db_session, [key])

    headers = {"X-API-Key": key}
    for _ in range(10):
        assert client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers).status_code == 200
    response = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG, headers=headers)

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 0


def test_universe_refresh_rate_limit_returns_429_on_second_post(tmp_path, monkeypatch, db_session: Session):
    key = f"refresh-{uuid4().hex}"
    client = _client(tmp_path, monkeypatch, db_session, [key])

    first = client.post("/api/universe/refresh", headers={"X-API-Key": key})
    second = client.post("/api/universe/refresh", headers={"X-API-Key": key})

    assert first.status_code == 202
    assert second.status_code == 429


def test_distinct_api_keys_have_separate_rate_limit_buckets(tmp_path, monkeypatch, db_session: Session):
    key_a = f"refresh-a-{uuid4().hex}"
    key_b = f"refresh-b-{uuid4().hex}"
    client = _client(tmp_path, monkeypatch, db_session, [key_a, key_b])

    first_a = client.post("/api/universe/refresh", headers={"X-API-Key": key_a})
    second_a = client.post("/api/universe/refresh", headers={"X-API-Key": key_a})
    first_b = client.post("/api/universe/refresh", headers={"X-API-Key": key_b})

    assert first_a.status_code == 202
    assert second_a.status_code == 429
    assert first_b.status_code == 202


def test_backcompat_mode_ignores_unconfigured_api_key_headers_for_rate_limit(tmp_path, monkeypatch, db_session: Session):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'rate-backcompat.sqlite').as_posix()}")
    monkeypatch.delenv("ATLAS20_API_KEYS", raising=False)
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)

    statuses = [
        client.post(
            "/api/backtests/run",
            json=DEFAULT_BACKTEST_CONFIG,
            headers={"X-API-Key": f"ignored-{index}"},
        ).status_code
        for index in range(11)
    ]

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


def test_cancel_route_rate_limited(tmp_path, monkeypatch, db_session: Session):
    key = f"cancel-{uuid4().hex}"
    client = _client(tmp_path, monkeypatch, db_session, [key])

    statuses = [
        client.post("/api/runs/btk_0148/cancel", headers={"X-API-Key": key}).status_code for _ in range(31)
    ]

    assert statuses[:30] == [202] * 30
    assert statuses[30] == 429


def test_favorite_route_rate_limited(tmp_path, monkeypatch, db_session: Session):
    key = f"favorite-{uuid4().hex}"
    client = _client(tmp_path, monkeypatch, db_session, [key])
    headers = {"X-API-Key": key}

    statuses = [
        client.post("/api/runs/btk_0142/favorite", headers=headers).status_code for _ in range(60)
    ]
    response = client.post("/api/runs/btk_0142/favorite", headers=headers)

    assert statuses == [200] * 60
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 0


JWT_SECRET = "rate-limit-jwt-secret-0123456789abcdef"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt(payload: dict[str, object], secret: str = JWT_SECRET) -> str:
    encoded_header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(secret.encode(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def _jwt_client(tmp_path, monkeypatch, db_session: Session, api_keys: list[str]) -> TestClient:
    monkeypatch.setenv("ATLAS20_JWT_AUTH_ENABLED", "true")
    monkeypatch.setenv("ATLAS20_JWT_SECRET_KEY", JWT_SECRET)
    return _client(tmp_path, monkeypatch, db_session, api_keys)


class _RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_rate_limit_warning_does_not_log_raw_api_key(tmp_path, monkeypatch, db_session: Session):
    key = f"k3y-super-secret-value-{uuid4().hex}"
    client = _client(tmp_path, monkeypatch, db_session, [key])
    handler = _RecordingHandler()
    slowapi_logger = logging.getLogger("slowapi")
    slowapi_logger.addHandler(handler)
    try:
        statuses = [client.post("/api/universe/refresh", headers={"X-API-Key": key}).status_code for _ in range(2)]
    finally:
        slowapi_logger.removeHandler(handler)

    assert statuses == [202, 429]
    assert any("exceeded" in message for message in handler.messages)
    assert all(key not in message for message in handler.messages)


def test_junk_api_key_headers_do_not_give_bearer_user_fresh_buckets(tmp_path, monkeypatch, db_session: Session):
    client = _jwt_client(tmp_path, monkeypatch, db_session, [f"configured-{uuid4().hex}"])
    token = _jwt({"sub": "researcher", "exp": 4_102_444_800})

    statuses = [
        client.post(
            "/api/universe/refresh",
            headers={"Authorization": f"Bearer {token}", "X-API-Key": f"junk-{index}"},
        ).status_code
        for index in range(2)
    ]

    assert statuses == [202, 429]


def test_distinct_tokens_for_one_principal_share_a_bucket(tmp_path, monkeypatch, db_session: Session):
    client = _jwt_client(tmp_path, monkeypatch, db_session, [])
    first = _jwt({"sub": "researcher", "exp": 4_102_444_800})
    second = _jwt({"sub": "researcher", "exp": 4_102_444_801})

    statuses = [
        client.post("/api/universe/refresh", headers={"Authorization": f"Bearer {token}"}).status_code
        for token in (first, second)
    ]

    assert first != second
    assert statuses == [202, 429]


def test_distinct_bearer_principals_have_separate_buckets(tmp_path, monkeypatch, db_session: Session):
    client = _jwt_client(tmp_path, monkeypatch, db_session, [])
    alice = _jwt({"sub": "alice", "exp": 4_102_444_800})
    bob = _jwt({"sub": "bob", "exp": 4_102_444_800})

    alice_statuses = [
        client.post("/api/universe/refresh", headers={"Authorization": f"Bearer {alice}"}).status_code for _ in range(2)
    ]
    bob_status = client.post("/api/universe/refresh", headers={"Authorization": f"Bearer {bob}"}).status_code

    assert alice_statuses == [202, 429]
    assert bob_status == 202


STRATEGY_LAB_BATCH = {
    "presets": ["base"],
    "topNs": [20],
    "rebalances": ["Monthly"],
    "baseConfig": {
        **DEFAULT_BACKTEST_CONFIG,
        "preset": "base",
        "window": {**DEFAULT_BACKTEST_CONFIG["window"], "rebalance": "Monthly"},
    },
}


def test_strategy_lab_batch_route_rate_limited(tmp_path, monkeypatch, db_session: Session):
    key = f"strategy-lab-{uuid4().hex}"
    client = _client(tmp_path, monkeypatch, db_session, [key])
    headers = {"X-API-Key": key}

    first = client.post("/api/strategy-lab/batches", json=STRATEGY_LAB_BATCH, headers=headers)
    second = client.post("/api/strategy-lab/batches", json=STRATEGY_LAB_BATCH, headers=headers)

    assert first.status_code == 202
    assert first.headers["X-RateLimit-Limit"] == "1"
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) >= 0
