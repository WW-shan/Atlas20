from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_python_development_uses_project_virtual_environment() -> None:
    agents = read("AGENTS.md")
    gitignore = read(".gitignore")
    makefile = read("Makefile")
    readme = read("README.md")
    contributing = read("CONTRIBUTING.md")
    verify_release = read("scripts/verify_release.py")

    assert ".venv/" in gitignore
    assert "Do not install Python dependencies into the system interpreter" in agents
    assert "python -m venv .venv" in agents
    assert ".venv/bin/python -m pip install -e \".[dev]\"" in agents

    assert "VENV ?= .venv" in makefile
    assert "PYTHON := $(VENV)/bin/python" in makefile
    assert "PIP := $(PYTHON) -m pip" in makefile
    assert "VENV_STAMP := $(VENV)/.installed" in makefile
    assert "setup:" in makefile
    assert "$(VENV_STAMP): pyproject.toml $(PYTHON)" in makefile
    assert "$(PYTHON) -m pytest" in makefile
    assert "$(PYTHON) -m atlas20.api.openapi" in makefile
    assert "\n\truff check src tests" not in makefile
    assert "$(PYTHON) -m ruff check src tests" in makefile
    assert "\n\tmypy --strict src/atlas20/api" not in makefile
    assert "$(PYTHON) -m mypy --strict src/atlas20/api" in makefile

    assert "python -m pip install -e \".[dev]\"" not in readme
    assert "python -m pip install -e \".[dev]\"" not in contributing
    assert "make setup" in readme
    assert "make setup" in contributing
    assert "npm --prefix apps/web ci" in contributing
    assert "npm --prefix apps/web install" not in contributing
    assert ".venv/bin/python -m atlas20.api.seed" in readme
    assert 'Run `make setup`, then rerun with `.venv/bin/python scripts/verify_release.py`.' in verify_release
    assert 'python -m pip install -e ".[dev]"' not in verify_release
