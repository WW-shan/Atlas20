from pathlib import Path

from fastapi.testclient import TestClient

from atlas20.api.app import create_app
from atlas20.api.settings import get_settings


def test_create_app_lifespan_resolves_alembic_from_clean_cwd(tmp_path, monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "startup.sqlite"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("ATLAS20_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
