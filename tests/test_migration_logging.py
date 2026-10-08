"""Startup migrations must not rewrite the app's logging configuration."""

from collections.abc import Iterator
import logging
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from atlas20.api.app import create_app
from atlas20.api.settings import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    return {
        "ATLAS20_DB_URL": f"sqlite:///{(tmp_path / 'atlas20.sqlite').as_posix()}",
        "ATLAS20_REPORT_ROOT": str(tmp_path / "reports"),
        "ATLAS20_DATA_ROOT": str(tmp_path / "data"),
        "ATLAS20_BACKUP_ROOT": str(tmp_path / "backups"),
        "ATLAS20_LOG_FILE_PATH": str(tmp_path / "logs" / "api.log"),
    }


@pytest.fixture
def restore_root_logging() -> Iterator[None]:
    root = logging.getLogger()
    saved_level = root.level
    saved_handlers = list(root.handlers)
    yield
    for handler in list(root.handlers):
        if handler not in saved_handlers:
            handler.close()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def test_startup_migrations_keep_app_root_logging(tmp_path, monkeypatch, restore_root_logging):
    for name, value in _isolated_env(tmp_path).items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    app = create_app()
    root = logging.getLogger()
    level_before = root.level
    handlers_before = list(root.handlers)
    formatters_before = [handler.formatter for handler in handlers_before]

    with TestClient(app):
        logging.getLogger("atlas20.api.test").info("after-startup-marker")

    assert root.level == level_before == logging.INFO
    assert root.handlers == handlers_before
    assert [handler.formatter for handler in root.handlers] == formatters_before
    for handler in root.handlers:
        handler.flush()
    assert "after-startup-marker" in (tmp_path / "logs" / "api.log").read_text(encoding="utf-8")


def test_alembic_cli_still_configures_its_own_logging(tmp_path):
    env = {**os.environ, **_isolated_env(tmp_path), "ATLAS20_DISABLE_SCHEDULER": "1"}

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(PROJECT_ROOT / "alembic.ini"), "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert "INFO  [alembic.runtime.migration] Running upgrade" in result.stderr
    assert (tmp_path / "atlas20.sqlite").is_file()
