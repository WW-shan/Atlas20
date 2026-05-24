"""Shared CSV parsing helpers for API data-access adapters."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError, ParserError


def _latest_report_dir(report_root: Path) -> Path:
    pointer = report_root / "latest.txt"
    if pointer.exists():
        try:
            target_name = pointer.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"Could not read {pointer}: {exc}") from exc
        if target_name:
            target = report_root / target_name
            resolved_root = report_root.resolve()
            resolved_target = target.resolve()
            try:
                resolved_target.relative_to(resolved_root)
            except ValueError as exc:
                raise ValueError(
                    f"latest.txt points outside report_root: {target_name!r}"
                ) from exc
            if target.exists():
                return target
    fallback = report_root / "latest"
    return fallback if fallback.exists() else report_root


def _read_csv(path: Path, *, index_col: int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required report CSV: {path}")
    try:
        frame = pd.read_csv(path, index_col=index_col)
    except EmptyDataError as exc:
        raise ValueError(f"Report CSV is empty: {path}") from exc
    except ParserError as exc:
        raise ValueError(f"Report CSV is malformed: {path}") from exc
    if frame.empty:
        raise ValueError(f"Report CSV has no rows: {path}")
    return frame


def _read_processed_csv(data_root: Path, filename: str) -> pd.DataFrame:
    path = data_root / "processed" / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing required processed CSV: {path}")
    try:
        frame = pd.read_csv(path)
    except EmptyDataError as exc:
        raise ValueError(f"Processed CSV is empty: {path}") from exc
    except ParserError as exc:
        raise ValueError(f"Processed CSV is malformed: {path}") from exc
    if frame.empty:
        raise ValueError(f"Processed CSV has no rows: {path}")
    return frame


def _load_date_indexed_csv(path: Path) -> pd.DataFrame:
    frame = _read_csv(path, index_col=0)
    frame.index = pd.to_datetime(frame.index, errors="coerce")
    if frame.index.isna().any():
        raise ValueError(f"{path} has invalid dates in the first column")
    if not len(frame.columns):
        raise ValueError(f"{path} has no strategy columns")
    frame = frame.sort_index()
    return frame.apply(pd.to_numeric, errors="raise")


def _date_string(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _as_float(value: Any, column: str | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        if column is None:
            raise ValueError(f"Invalid numeric value: {value!r}") from exc
        raise ValueError(f"Invalid numeric value in {column}: {value!r}") from exc
    if not math.isfinite(result):
        if column is None:
            raise ValueError(f"Non-finite numeric value: {value!r}")
        raise ValueError(f"Non-finite numeric value in {column}: {value!r}")
    return result


def _as_text(value: Any, column: str) -> str:
    if pd.isna(value):
        raise ValueError(f"Missing text value in {column}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Missing text value in {column}")
    return text


_DISPLAY_NAME_OVERRIDES = {
    "base": "Base Config",
    "universe_refresh": "Universe Refresh",
}
_STRATEGY_FAMILY_PREFIXES: list[tuple[str, str]] = [
    ("BTC_BH", "BTC Benchmark"),
    ("ETH_BH", "ETH Benchmark"),
    ("TOP20_EQ", "Equal Weight"),
    ("TOP20_MOM", "Momentum Rotation"),
    ("TOP20_SECTOR", "Sector Rotation"),
]


def _strategy_family(name: str) -> str:
    for prefix, label in _STRATEGY_FAMILY_PREFIXES:
        if name.startswith(prefix):
            return label
    return "Other"


def _format_display_name(strategy: str) -> str:
    slug = strategy.strip().replace("_", "")
    if not slug:
        return strategy
    if strategy.strip() in _DISPLAY_NAME_OVERRIDES:
        return _DISPLAY_NAME_OVERRIDES[strategy.strip()]

    family = _strategy_family(strategy)
    for prefix, _ in _STRATEGY_FAMILY_PREFIXES:
        if strategy.startswith(prefix):
            variant = strategy[len(prefix):].lstrip("_")
            if not variant:
                return family
            cleaned = variant.replace("__", " \u00b7 ").replace("_", " ")
            return f"{family} \u00b7 {cleaned.title()}"
    return strategy.replace("__", " \u00b7 ").replace("_", " ").title()
