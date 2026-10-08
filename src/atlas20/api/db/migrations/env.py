from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel

from atlas20.api.db import models as _models  # noqa: F401
from atlas20.api.settings import get_settings

config = context.config


def _should_configure_logging() -> bool:
    # fileConfig() replaces the root logger's level and handlers (closing the
    # old ones). That suits the `alembic` CLI, but the API lifespan and the
    # seed CLI run command.upgrade() in-process after configure_logging();
    # rewriting root there drops INFO logs, closes the log file handler and
    # bypasses redaction. Only the CLI sets cmd_opts; programmatic callers can
    # still opt in with config.attributes["configure_logger"] = True.
    configure_logger = config.attributes.get("configure_logger")
    if configure_logger is not None:
        return bool(configure_logger)
    return config.cmd_opts is not None


if config.config_file_name is not None and _should_configure_logging():
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def _settings_url() -> str:
    return get_settings().db_url


def _ensure_sqlite_parent(db_url: str) -> None:
    url = make_url(db_url)
    database = url.database
    if url.get_backend_name() != "sqlite" or database is None or database in ("", ":memory:"):
        return
    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    url = _settings_url()
    _ensure_sqlite_parent(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _settings_url()
    _ensure_sqlite_parent(url)
    config.set_main_option("sqlalchemy.url", url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
