"""Alembic migration helpers shared by API startup and CLIs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock
from sqlalchemy.engine import make_url

from atlas20.api.settings import Settings

if TYPE_CHECKING:
    from alembic.config import Config


def alembic_config(settings: Settings) -> Config:
    from alembic.config import Config

    cwd_config = Path("alembic.ini")
    root_config = Path(settings.project_root) / "alembic.ini"
    config_path = cwd_config if cwd_config.exists() else root_config
    cfg = Config(str(config_path))
    script_location = cfg.get_main_option("script_location") if hasattr(cfg, "get_main_option") else None
    if script_location and ":" not in script_location and hasattr(cfg, "set_main_option"):
        script_path = Path(script_location)
        if not script_path.is_absolute():
            cfg.set_main_option("script_location", str((config_path.parent / script_path).resolve()))
    return cfg


def upgrade_to_head(settings: Settings) -> None:
    from alembic import command

    url = make_url(settings.db_url)
    if url.drivername.startswith("sqlite") and url.database:
        db_path = Path(url.database)
        lock_path = db_path.with_suffix(".alembic.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path), timeout=60):
            command.upgrade(alembic_config(settings), "head")
    else:
        command.upgrade(alembic_config(settings), "head")
