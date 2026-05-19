"""Universe API adapters backed by processed data CSV artifacts."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from atlas20.api.data_access._common import _date_string, _read_processed_csv
from atlas20.api.settings import Settings


REBALANCE_COLUMNS = {"symbol", "rebalance_date", "universe_rank"}
DATA_QUALITY_COLUMNS = {
    "symbol",
    "validation_passed",
    "validation_reason",
    "latest_overlap_date",
    "latest_price_gap",
    "price_correlation",
    "included_in_panel",
}
MAJOR_ROTATION_SYMBOL_DIFF_THRESHOLD = 3
UNIVERSE_TOKEN_LIMIT = 20
ROTATION_LIMIT = 6
ALERT_LIMIT = 12
SEVERITY_RANK = {"rose": 0, "cyan": 1, "emerald": 2}


def load_universe_timeline_from_processed(settings: Settings) -> dict[str, Any]:
    """Build UniverseTimelinePayload data from processed rebalance_universe.csv."""
    frame = _read_processed_csv(settings.data_root, "rebalance_universe.csv")
    frame = _parse_rebalance_frame(frame, settings.data_root / "processed" / "rebalance_universe.csv")

    latest_date = frame["rebalance_date"].max()
    # Inclusive cutoff matches the Batch 4 brief's data-anchored 180-day window.
    window_start = latest_date - pd.Timedelta(days=180)
    window = frame[(frame["rebalance_date"] >= window_start) & (frame["rebalance_date"] <= latest_date)].copy()
    if window.empty:
        raise ValueError("rebalance_universe.csv has no rows in the latest 180-day window")

    window_dates = sorted(window["rebalance_date"].drop_duplicates().tolist())
    top_ranked = window[window["universe_rank"] <= UNIVERSE_TOKEN_LIMIT].copy()
    appearances = top_ranked[["symbol", "rebalance_date"]].drop_duplicates()
    tokens = _rank_tokens_by_frequency(appearances)

    return {
        "tokens": tokens,
        "segments": _build_segments(tokens, appearances, window_dates),
        "rotations": _build_rotations(top_ranked),
        "range": {"start": _date_string(window_dates[0]), "end": _date_string(latest_date)},
    }


def load_data_alerts_from_processed(settings: Settings) -> list[dict[str, Any]]:
    """Build DataAlert rows from processed data_quality.csv."""
    path = settings.data_root / "processed" / "data_quality.csv"
    frame = _read_processed_csv(settings.data_root, "data_quality.csv")
    _require_columns(frame, DATA_QUALITY_COLUMNS, path)

    alerts: list[tuple[int, str, dict[str, Any]]] = []
    for _, row in frame.iterrows():
        symbol = _as_symbol(row["symbol"], "symbol")
        validation_passed = _as_bool(row["validation_passed"], "validation_passed")
        latest_overlap_date = _date_string(_as_date(row["latest_overlap_date"], "latest_overlap_date"))
        included_in_panel = _as_bool(row["included_in_panel"], "included_in_panel")

        alert = _alert_from_quality_row(row, symbol, validation_passed, latest_overlap_date, included_in_panel)
        if alert is not None:
            alerts.append((SEVERITY_RANK[alert["severity"]], symbol, alert))

    alerts.sort(key=lambda item: (item[0], item[1]))
    return [alert for _, _, alert in alerts[:ALERT_LIMIT]]


def _parse_rebalance_frame(frame: pd.DataFrame, path: Path) -> pd.DataFrame:
    _require_columns(frame, REBALANCE_COLUMNS, path)
    parsed = frame.copy()
    parsed["symbol"] = parsed["symbol"].map(lambda value: _as_symbol(value, "symbol"))
    parsed["rebalance_date"] = _parse_datetime_column(parsed["rebalance_date"], path, "rebalance_date")
    try:
        parsed["universe_rank"] = pd.to_numeric(parsed["universe_rank"], errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path} has invalid numeric values in universe_rank") from exc
    if parsed["universe_rank"].isna().any():
        raise ValueError(f"{path} has missing numeric values in universe_rank")
    return parsed.sort_values(["rebalance_date", "universe_rank", "symbol"])


def _parse_datetime_column(series: pd.Series, path: Path, column: str) -> pd.Series:
    dates = pd.to_datetime(series, errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{path} has invalid dates in {column}")
    return dates.dt.normalize()


def _require_columns(frame: pd.DataFrame, columns: set[str], path: Path) -> None:
    missing = columns - set(frame.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"{path} missing required columns: {missing_cols}")


def _rank_tokens_by_frequency(appearances: pd.DataFrame) -> list[str]:
    if appearances.empty:
        return []
    frequencies = appearances.groupby("symbol").size().reset_index(name="frequency")
    # Symbol tie-break keeps output deterministic when frequencies match.
    frequencies = frequencies.sort_values(["frequency", "symbol"], ascending=[False, True])
    return [str(symbol) for symbol in frequencies["symbol"].head(UNIVERSE_TOKEN_LIMIT)]


def _build_segments(tokens: list[str], appearances: pd.DataFrame, window_dates: list[pd.Timestamp]) -> list[dict[str, str]]:
    if appearances.empty:
        return []

    date_positions = {value: index for index, value in enumerate(window_dates)}
    segments: list[dict[str, str]] = []
    for token in tokens:
        token_dates = sorted(appearances.loc[appearances["symbol"] == token, "rebalance_date"].drop_duplicates().tolist())
        if not token_dates:
            continue

        start = previous = token_dates[0]
        for current in token_dates[1:]:
            if date_positions[current] == date_positions[previous] + 1:
                previous = current
                continue
            segments.append({"token": token, "start": _date_string(start), "end": _date_string(previous)})
            start = previous = current
        segments.append({"token": token, "start": _date_string(start), "end": _date_string(previous)})
    return segments


def _build_rotations(top_ranked: pd.DataFrame) -> list[dict[str, str]]:
    if top_ranked.empty:
        return []

    rotations: list[dict[str, str]] = []
    previous_symbols: set[str] | None = None
    rebalance_dates = sorted(top_ranked["rebalance_date"].drop_duplicates().tolist())
    for rebalance_date in rebalance_dates:
        current_symbols = set(top_ranked.loc[top_ranked["rebalance_date"] == rebalance_date, "symbol"])
        if (
            previous_symbols is not None
            and len(current_symbols.symmetric_difference(previous_symbols)) >= MAJOR_ROTATION_SYMBOL_DIFF_THRESHOLD
        ):
            rotations.append({"ts": _date_string(rebalance_date), "label": "MAJOR ROTATION"})
        previous_symbols = current_symbols
    return rotations[-ROTATION_LIMIT:]  # six most recent, preserving chronological order


def _alert_from_quality_row(
    row: pd.Series,
    symbol: str,
    validation_passed: bool,
    latest_overlap_date: str,
    included_in_panel: bool,
) -> dict[str, str] | None:
    meta = f"latest overlap: {latest_overlap_date} · panel included: {'yes' if included_in_panel else 'no'}"
    ts = f"{latest_overlap_date}T00:00:00Z"

    if not validation_passed:
        reason = _as_text(row["validation_reason"], default="validation failed")
        return {
            "id": f"dq_{symbol.lower()}",
            "severity": "rose",
            "title": f"{symbol} · {reason} — review required",
            "meta": meta,
            "ts": ts,
            "icon": "alert-triangle",
        }

    price_correlation = _as_float(row["price_correlation"], "price_correlation")
    if price_correlation < 0.98:
        return {
            "id": f"dq_{symbol.lower()}",
            "severity": "cyan",
            "title": f"{symbol} · price correlation {price_correlation:.3f} below 0.98",
            "meta": meta,
            "ts": ts,
            "icon": "info",
        }

    latest_price_gap = _as_float(row["latest_price_gap"], "latest_price_gap")
    if latest_price_gap > 0.005:
        return {
            "id": f"dq_{symbol.lower()}",
            "severity": "cyan",
            "title": f"{symbol} · latest price gap {latest_price_gap:.2%}",
            "meta": meta,
            "ts": ts,
            "icon": "info",
        }

    return None


def _as_symbol(value: Any, column: str) -> str:
    if pd.isna(value):
        raise ValueError(f"Missing text value in {column}")
    symbol = str(value).strip()
    if not symbol:
        raise ValueError(f"Missing text value in {column}")
    return symbol


def _as_text(value: Any, *, default: str) -> str:
    if pd.isna(value):
        return default
    text = str(value).strip()
    return text or default


def _as_bool(value: Any, column: str) -> bool:
    if pd.isna(value):
        raise ValueError(f"Missing boolean value in {column}")
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean value in {column}: {value!r}")


def _as_date(value: Any, column: str) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid date value in {column}: {value!r}")
    return pd.Timestamp(parsed)


def _as_float(value: Any, column: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value in {column}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite numeric value in {column}: {value!r}")
    return result

