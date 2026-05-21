"""Tests for the shadow-install warning emitted from app lifespan startup."""
from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from atlas20.api import app as app_module


def test_warn_when_installed_copy_shadows_repo_src(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When site-packages copy shadows repo src/, lifespan must warn so devs
    notice their edits are not running. Smoke uncovered this exact failure
    mode: uvicorn loaded compare.py from site-packages even though the repo
    had the post-B16 fix in src/."""
    repo_src = tmp_path / "src" / "atlas20"
    repo_src.mkdir(parents=True)
    (repo_src / "__init__.py").write_text("", encoding="utf-8")

    stale_install = tmp_path / "site-packages" / "atlas20"
    stale_install.mkdir(parents=True)
    stale_file = stale_install / "__init__.py"
    stale_file.write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        app_module,
        "atlas20",
        SimpleNamespace(__file__=str(stale_file)),
        raising=False,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "atlas20",
        SimpleNamespace(__file__=str(stale_file)),
    )

    with caplog.at_level(logging.WARNING, logger="atlas20.api.install_check"):
        app_module._warn_if_shadow_install()

    assert "stale installed copy" in caplog.text
    assert str(stale_file) in caplog.text


def test_no_warning_when_no_repo_src(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Docker runs from /app where src/atlas20/__init__.py does NOT exist
    (only src/atlas20/api/db/migrations/ is copied). Production deployments
    must not see this warning."""
    monkeypatch.chdir(tmp_path)

    with caplog.at_level(logging.WARNING, logger="atlas20.api.install_check"):
        app_module._warn_if_shadow_install()

    assert "stale installed copy" not in caplog.text


def test_no_warning_when_loaded_from_repo_src(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PYTHONPATH=src or editable install: atlas20.__file__ already lives
    under cwd/src/atlas20/. No warning expected."""
    repo_src = tmp_path / "src" / "atlas20"
    repo_src.mkdir(parents=True)
    init_file = repo_src / "__init__.py"
    init_file.write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(
        __import__("sys").modules,
        "atlas20",
        SimpleNamespace(__file__=str(init_file)),
    )

    with caplog.at_level(logging.WARNING, logger="atlas20.api.install_check"):
        app_module._warn_if_shadow_install()

    assert "stale installed copy" not in caplog.text
