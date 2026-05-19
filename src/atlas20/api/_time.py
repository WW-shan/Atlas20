"""Project-wide time helpers; keep direct clock access in this module."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from atlas20.api.settings import get_settings


def today() -> date:
    settings = get_settings()
    if settings.anchor_date is not None:
        return settings.anchor_date
    return datetime.now(timezone.utc).date()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_iso_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_iso_from_path_mtime(path: Path) -> str:
    return utc_iso_from_timestamp(path.stat().st_mtime)
