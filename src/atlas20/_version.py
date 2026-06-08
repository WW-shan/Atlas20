"""Package version helpers."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib


def _read_pyproject_version() -> str:
    for parent in Path(__file__).resolve().parents:
        pyproject = parent / "pyproject.toml"
        if not pyproject.exists():
            continue
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        project = data.get("project", {})
        raw_version = project.get("version")
        if isinstance(raw_version, str) and raw_version:
            return raw_version
    return "unknown"


def _distribution_version() -> str:
    try:
        return version("atlas20-rotation")
    except PackageNotFoundError:
        return _read_pyproject_version()


__version__ = _distribution_version()
