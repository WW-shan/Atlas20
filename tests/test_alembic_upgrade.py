from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from atlas20.api.settings import get_settings


def test_alembic_upgrade_creates_expected_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "atlas20.sqlite"
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    tables = set(inspect(engine).get_table_names())

    assert {"runs", "report_files", "kv_settings", "idempotency_keys"}.issubset(tables)
