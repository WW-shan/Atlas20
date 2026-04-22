"""Logging helpers for the Atlas20 project."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(level: str = "INFO") -> None:
    """Configure a consistent project-wide logger."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module logger."""
    return logging.getLogger(name)


def ensure_dir(path: Path) -> Path:
    """Create a directory if it does not already exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path
