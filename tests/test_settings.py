from datetime import date
from pathlib import Path

from atlas20.api.settings import Settings
from atlas20.api.settings import get_settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("ATLAS20_ANCHOR_DATE", raising=False)

    settings = Settings()

    assert settings.env == "dev"
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert settings.db_url == "sqlite:///./data/atlas20.sqlite"
    assert settings.secret_key == "dev-only-do-not-use-in-prod"
    assert settings.api_keys == set()
    assert settings.enable_docs is True
    assert settings.report_root.name == "reports"
    assert settings.backup_root.name == "backups"
    assert settings.backup_retention_days == 30
    assert settings.data_root.name == "data"
    assert settings.anchor_date is None
    assert settings.log_level == "INFO"
    assert settings.log_format == "json"


def test_settings_project_root_defaults_to_repo_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.project_root == Path(__file__).resolve().parents[1]
    assert settings.project_root.name == "Atlas20"


def test_settings_accepts_custom_cors_origins():
    settings = Settings(cors_origins=["https://example.com"])

    assert settings.cors_origins == ["https://example.com"]


def test_settings_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("ATLAS20_CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("ATLAS20_API_KEYS", '["key-a", "key-b"]')
    monkeypatch.setenv("ATLAS20_ENABLE_DOCS", "false")
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", "2026-05-19")
    monkeypatch.setenv("ATLAS20_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.cors_origins == ["https://example.com"]
    assert settings.api_keys == {"key-a", "key-b"}
    assert settings.enable_docs is False
    assert settings.anchor_date == date(2026, 5, 19)
    assert settings.log_level == "DEBUG"


def test_settings_accepts_anchor_date():
    settings = Settings(anchor_date=date(2026, 5, 19))

    assert settings.anchor_date == date(2026, 5, 19)


def test_prod_docs_can_be_disabled(monkeypatch):
    from fastapi.testclient import TestClient

    from atlas20.api.app import create_app

    monkeypatch.setenv("ATLAS20_ENV", "prod")
    monkeypatch.setenv("ATLAS20_ENABLE_DOCS", "false")
    get_settings.cache_clear()

    client = TestClient(create_app())

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
