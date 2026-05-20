from uuid import uuid4

from fastapi.testclient import TestClient
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
