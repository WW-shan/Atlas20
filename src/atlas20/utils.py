"""Shared utility helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


def normalize_date_index(index: Iterable[pd.Timestamp | str]) -> pd.DatetimeIndex:
    """Return a normalized daily DatetimeIndex."""
    return pd.to_datetime(index).tz_localize(None).normalize()


def annualization_factor(days: int = 365) -> float:
    """Return the annualization factor for daily crypto series."""
    return float(days)


def slugify(value: str) -> str:
    """Convert a string into a filesystem-friendly slug."""
    return (
        value.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("__", "_")
        .replace("-", "_")
    )


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    """Persist a DataFrame as CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
