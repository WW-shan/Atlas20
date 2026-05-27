from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

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
    assert settings.jwt_auth_enabled is False
    assert settings.jwt_secret_key is None
    assert settings.jwt_issuer is None
    assert settings.jwt_audience is None
    assert settings.jwt_leeway_seconds == 30
    assert settings.cors_allow_credentials is True
    assert settings.enable_docs is True
    assert settings.report_root.name == "reports"
    assert settings.backup_root.name == "backups"
    assert settings.backup_retention_days == 30
    assert settings.data_root.name == "data"
    assert settings.anchor_date is None
    assert settings.log_level == "INFO"
    assert settings.log_format == "json"
    assert settings.worker_heartbeat_interval_seconds == 2.0
    assert settings.worker_cancel_grace_seconds == 3.0


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
    monkeypatch.setenv("ATLAS20_API_KEYS", "key-a,key-b")
    monkeypatch.setenv("ATLAS20_ENABLE_DOCS", "false")
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", "2026-05-19")
    monkeypatch.setenv("ATLAS20_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ATLAS20_WORKER_HEARTBEAT_INTERVAL_SECONDS", "0.1")
    monkeypatch.setenv("ATLAS20_WORKER_CANCEL_GRACE_SECONDS", "0.2")
    monkeypatch.setenv("ATLAS20_JWT_AUTH_ENABLED", "true")
    monkeypatch.setenv("ATLAS20_JWT_SECRET_KEY", "jwt-secret")
    monkeypatch.setenv("ATLAS20_JWT_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ATLAS20_JWT_AUDIENCE", "atlas20-api")
    monkeypatch.setenv("ATLAS20_JWT_LEEWAY_SECONDS", "45")

    settings = Settings()

    assert settings.cors_origins == ["https://example.com"]
    assert settings.api_keys == {"key-a", "key-b"}
    assert settings.enable_docs is False
    assert settings.anchor_date == date(2026, 5, 19)
    assert settings.log_level == "DEBUG"
    assert settings.worker_heartbeat_interval_seconds == 0.1
    assert settings.worker_cancel_grace_seconds == 0.2
    assert settings.jwt_auth_enabled is True
    assert settings.jwt_secret_key == "jwt-secret"
    assert settings.jwt_issuer == "https://auth.example.com"
    assert settings.jwt_audience == "atlas20-api"
    assert settings.jwt_leeway_seconds == 45


def test_settings_accepts_anchor_date():
    settings = Settings(anchor_date=date(2026, 5, 19))

    assert settings.anchor_date == date(2026, 5, 19)


def test_prod_requires_explicit_cors_origins(monkeypatch):
    monkeypatch.setenv("ATLAS20_ENV", "prod")
    monkeypatch.delenv("ATLAS20_CORS_ORIGINS", raising=False)

    with pytest.raises(ValidationError, match="ATLAS20_CORS_ORIGINS must be set in prod"):
        Settings()


def test_prod_forces_docs_disabled():
    settings = Settings(
        env="prod",
        cors_origins=["https://example.com"],
        secret_key="prod-secret",
        api_keys={"prod-key"},
        enable_docs=True,
    )

    assert settings.enable_docs is False


def test_prod_rejects_wildcard_cors_origins():
    with pytest.raises(ValidationError, match="must not include"):
        Settings(env="prod", cors_origins=["*"], secret_key="prod-secret")


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://localhost",
        "https://localhost:5173",
        "http://127.0.0.1",
        "http://127.0.0.2",
        "http://[::1]:5173",
    ],
)
def test_prod_rejects_dev_cors_origins(origin):
    with pytest.raises(ValidationError, match="dev origins are not allowed in prod"):
        Settings(env="prod", cors_origins=[origin], secret_key="prod-secret")


def test_prod_accepts_specific_origin_with_credentials_enabled():
    settings = Settings(
        env="prod",
        cors_origins=["https://example.com"],
        cors_allow_credentials=True,
        secret_key="prod-secret",
        api_keys={"prod-key"},
    )

    assert settings.cors_origins == ["https://example.com"]
    assert settings.cors_allow_credentials is True


def test_rejects_wildcard_cors_origins_with_credentials_enabled():
    with pytest.raises(ValidationError, match=r"must not include '\*' when credentials are allowed"):
        Settings(env="prod", cors_origins=["*"], cors_allow_credentials=True, secret_key="prod-secret")


def test_dev_accepts_dev_cors_origins():
    settings = Settings(env="dev", cors_origins=["http://localhost:5173", "http://127.0.0.1:5173"])

    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_prod_rejects_default_secret_key():
    with pytest.raises(ValidationError, match="ATLAS20_SECRET_KEY must be set to a real secret in prod"):
        Settings(env="prod", cors_origins=["https://example.com"])


def test_prod_accepts_explicit_secret_key():
    settings = Settings(
        env="prod",
        cors_origins=["https://example.com"],
        secret_key="prod-secret",
        api_keys={"prod-key"},
    )

    assert settings.secret_key == "prod-secret"


def test_prod_requires_api_key_or_jwt_auth():
    with pytest.raises(ValidationError, match="ATLAS20_API_KEYS or ATLAS20_JWT_AUTH_ENABLED must configure authentication in prod"):
        Settings(env="prod", cors_origins=["https://example.com"], secret_key="prod-secret")


def test_prod_accepts_non_empty_api_keys():
    settings = Settings(
        env="prod",
        cors_origins=["https://example.com"],
        secret_key="prod-secret",
        api_keys={"prod-key"},
    )

    assert settings.api_keys == {"prod-key"}


def test_prod_accepts_jwt_auth_without_api_keys():
    settings = Settings(
        env="prod",
        cors_origins=["https://example.com"],
        secret_key="prod-secret",
        jwt_auth_enabled=True,
    )

    assert settings.jwt_auth_enabled is True
    assert settings.api_keys == set()


def test_dev_accepts_empty_api_keys():
    settings = Settings(env="dev", api_keys=set())

    assert settings.api_keys == set()


def test_prod_docs_can_be_disabled(monkeypatch):
    from fastapi.testclient import TestClient

    from atlas20.api.app import create_app

    monkeypatch.setenv("ATLAS20_ENV", "prod")
    monkeypatch.setenv("ATLAS20_CORS_ORIGINS", "https://example.com")
    monkeypatch.setenv("ATLAS20_SECRET_KEY", "prod-secret")
    monkeypatch.setenv("ATLAS20_API_KEYS", "prod-key")
    monkeypatch.setenv("ATLAS20_ENABLE_DOCS", "false")
    get_settings.cache_clear()

    client = TestClient(create_app())

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_prod_docs_are_disabled_even_when_enabled_in_env(monkeypatch):
    from fastapi.testclient import TestClient

    from atlas20.api.app import create_app

    monkeypatch.setenv("ATLAS20_ENV", "prod")
    monkeypatch.setenv("ATLAS20_CORS_ORIGINS", "https://example.com")
    monkeypatch.setenv("ATLAS20_SECRET_KEY", "prod-secret")
    monkeypatch.setenv("ATLAS20_API_KEYS", "prod-key")
    monkeypatch.setenv("ATLAS20_ENABLE_DOCS", "true")
    get_settings.cache_clear()

    client = TestClient(create_app())

    assert client.get("/docs").status_code == 404
