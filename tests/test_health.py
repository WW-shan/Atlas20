from fastapi.testclient import TestClient

from atlas20.api.app import create_app
from atlas20.api.repositories import get_session
from atlas20.api.settings import get_settings


def _app(tmp_path, monkeypatch):
    report_root = tmp_path / "reports"
    data_root = tmp_path / "data"
    report_root.mkdir()
    data_root.mkdir()
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(data_root))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'health.sqlite').as_posix()}")
    get_settings.cache_clear()
    return create_app()


def test_healthz_returns_ok(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_ready_when_checks_pass(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"db": "ok", "reports": "ok"}}


def test_readyz_returns_503_when_db_check_fails(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)

    class BrokenSession:
        def exec(self, statement):
            del statement
            raise RuntimeError("db down")

    def override_get_session():
        yield BrokenSession()

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"]["db"] == "fail"


def test_readyz_returns_503_when_report_root_is_not_writable(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)

    from atlas20.api.routes import health

    with TestClient(app) as client:
        monkeypatch.setattr(health, "_is_report_root_writable", lambda path: False)
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"]["reports"] == "fail"
