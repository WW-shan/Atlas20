from fastapi.testclient import TestClient

from atlas20.api import app as app_module
from atlas20.api.settings import get_settings


class DummyConfig:
    def __init__(self, path: str):
        self.path = path


def test_lifespan_skips_file_lock_for_non_sqlite(monkeypatch):
    monkeypatch.setenv("ATLAS20_DB_URL", "postgresql://user@host/db")
    get_settings.cache_clear()
    upgrades = []

    def forbidden_file_lock(*args, **kwargs):
        raise AssertionError("non-sqlite db_url must not use FileLock")

    monkeypatch.setattr(app_module, "FileLock", forbidden_file_lock)
    monkeypatch.setattr("alembic.config.Config", DummyConfig)
    monkeypatch.setattr("alembic.command.upgrade", lambda cfg, revision: upgrades.append((cfg.path, revision)))

    try:
        with TestClient(app_module.create_app()):
            pass
    finally:
        get_settings.cache_clear()

    assert upgrades == [("alembic.ini", "head")]
