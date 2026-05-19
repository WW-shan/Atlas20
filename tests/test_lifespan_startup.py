from filelock import FileLock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from atlas20.api.app import create_app
from atlas20.api.settings import get_settings


def test_lifespan_runs_migrations_under_file_lock(tmp_path, monkeypatch):
    db_path = tmp_path / "atlas20.sqlite"
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()

    with TestClient(create_app()):
        pass

    tables = set(inspect(create_engine(f"sqlite:///{db_path.as_posix()}")).get_table_names())
    assert {"runs", "report_files", "kv_settings", "idempotency_keys"}.issubset(tables)

    lock_path = db_path.with_suffix(".alembic.lock")
    with FileLock(str(lock_path), timeout=1):
        assert lock_path.exists()
