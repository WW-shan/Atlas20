"""Options payload adapter backed by report and processed CSV artifacts."""

from __future__ import annotations

from typing import Any

import pandas as pd

from atlas20.api.data_access.overview import _as_float, _latest_report_dir, _read_csv
from atlas20.api.data_access.universe import _read_processed_csv
from atlas20.api.settings import Settings


SUMMARY_COLUMNS = {"strategy", "sharpe"}
REBALANCE_COLUMNS = {"sector", "rebalance_date"}
FEE_BPS_RANGE = [0.0, 10.0, 50.0]
SLIPPAGE_BPS_RANGE = [0.0, 5.0, 25.0]
UNIVERSES = [
    {"topN": 5, "label": "Top 5"},
    {"topN": 10, "label": "Top 10"},
    {"topN": 20, "label": "Top 20"},
]
REBALANCES = [
    {"value": "Weekly", "label": "Weekly"},
    {"value": "Biweekly", "label": "Biweekly"},
    {"value": "Monthly", "label": "Monthly"},
]


def load_options_from_reports(settings: Settings) -> dict[str, Any]:
    """Build OptionsPayload from summary and latest rebalance universe CSVs."""
    return {
        "presets": _load_presets(settings),
        "universes": UNIVERSES,
        "rebalances": REBALANCES,
        "feeBpsRange": FEE_BPS_RANGE,
        "slippageBpsRange": SLIPPAGE_BPS_RANGE,
        "sectors": _load_latest_sectors(settings),
    }


def _load_presets(settings: Settings) -> list[str]:
    path = _latest_report_dir(settings.report_root) / "strategy_summary.csv"
    frame = _read_csv(path)
    missing = SUMMARY_COLUMNS - set(frame.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"{path} missing required columns: {missing_cols}")

    parsed = frame.copy()
    parsed["strategy"] = parsed["strategy"].map(lambda value: _as_text(value, "strategy"))
    try:
        parsed["sharpe"] = pd.to_numeric(parsed["sharpe"], errors="raise")
        parsed["sharpe"] = parsed["sharpe"].map(_as_float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path} has invalid numeric values in sharpe") from exc

    ranked = parsed.sort_values(["sharpe", "strategy"], ascending=[False, True])
    return [str(strategy) for strategy in ranked["strategy"].head(30)]


def _load_latest_sectors(settings: Settings) -> list[str]:
    path = settings.data_root / "processed" / "rebalance_universe.csv"
    frame = _read_processed_csv(settings.data_root, "rebalance_universe.csv")
    missing = REBALANCE_COLUMNS - set(frame.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"{path} missing required columns: {missing_cols}")

    parsed = frame.copy()
    parsed["rebalance_date"] = pd.to_datetime(parsed["rebalance_date"], errors="coerce")
    if parsed["rebalance_date"].isna().any():
        raise ValueError(f"{path} has invalid dates in rebalance_date")

    latest_date = parsed["rebalance_date"].max()
    latest = parsed[parsed["rebalance_date"] == latest_date]
    sectors = {_as_optional_text(value) for value in latest["sector"]}
    return sorted(sector for sector in sectors if sector)


def _as_text(value: Any, column: str) -> str:
    if pd.isna(value):
        raise ValueError(f"Missing text value in {column}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Missing text value in {column}")
    return text


def _as_optional_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()
