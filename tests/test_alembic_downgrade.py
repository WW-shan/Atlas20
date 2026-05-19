from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from atlas20.api.settings import get_settings


EXPECTED_TABLES = {"runs", "report_files", "kv_settings", "idempotency_keys"}


def test_alembic_downgrade_base_drops_application_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "atlas20.sqlite"
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))
    engine.dispose()

    command.downgrade(cfg, "base")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    assert EXPECTED_TABLES.isdisjoint(set(inspect(engine).get_table_names()))
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))
    engine.dispose()
