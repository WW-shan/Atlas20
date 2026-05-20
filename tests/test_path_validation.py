from fastapi.testclient import TestClient
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.repositories import get_session
from atlas20.api.settings import get_settings


def _client(tmp_path, monkeypatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'path.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def test_cancel_route_rejects_malformed_run_id(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)

    response = client.post("/api/runs/not_a_run/cancel")

    assert response.status_code == 422


def test_cancel_route_accepts_valid_run_id(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)

    response = client.post("/api/runs/btk_0148/cancel")

    assert response.status_code in {202, 409}


def test_report_download_rejects_malformed_report_id(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)

    response = client.get("/api/reports/UPPER/download")

    assert response.status_code == 422


def test_report_download_rejects_valid_but_missing_report_id(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)

    response = client.get("/api/reports/r2/download")

    assert response.status_code == 404
