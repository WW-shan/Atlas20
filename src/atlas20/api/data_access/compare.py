"""Compare payload adapter backed by report CSV artifacts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from atlas20.api.data_access.overview import _as_float, _date_string, _latest_report_dir, _load_date_indexed_csv, _read_csv
from atlas20.api.data_access.universe import _read_processed_csv
from atlas20.api.settings import Settings


SUMMARY_COLUMNS = {
    "strategy",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe",
    "sortino",
    "max_drawdown",
    "calmar",
    "monthly_win_rate",
    "annualized_turnover",
    "avg_turnover_per_rebalance",
    "average_holdings",
}
NUMERIC_SUMMARY_COLUMNS = SUMMARY_COLUMNS - {"strategy"}
BENCHMARK_PREFIXES = ("BTC_BH", "ETH_BH")
ALIAS_IDS = {"atlas", "momentum", "meanrev"}
RANGE_DAYS = {"1M": 30, "3M": 90, "1Y": 365}
VALID_RANGES = {"1M", "3M", "YTD", "1Y", "ALL"}
MAX_EQUITY_POINTS = 180
TOP_UNIVERSE_SIZE = 20


def load_compare_from_reports(settings: Settings, ids: list[str], range_: str) -> dict[str, Any]:
    """Build ComparePayload from strategy summary, equity curves, and latest universe."""
    summary_df = _load_compare_summary(settings)
    equity_curves_df = _load_compare_equity(settings)
    resolved_ids = _resolve_strategy_ids(ids, summary_df, equity_curves_df.columns)
    if not resolved_ids:
        raise ValueError("No compare ids resolved")

    window = _filter_equity_range(equity_curves_df[resolved_ids].dropna(), range_, settings)
    sampled = _downsample(window, max_points=MAX_EQUITY_POINTS)
    normalized = _normalize(sampled, resolved_ids)
    latest_universe = _load_latest_universe(settings)

    return {
        "equity": _build_equity_points(normalized, resolved_ids),
        "metrics": _build_metrics(summary_df, resolved_ids),
        "overlap": _build_overlap(resolved_ids, latest_universe),
    }


def _load_compare_summary(settings: Settings) -> pd.DataFrame:
    path = _latest_report_dir(settings.report_root) / "strategy_summary.csv"
    frame = _read_csv(path)
    missing = SUMMARY_COLUMNS - set(frame.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"{path} missing required columns: {missing_cols}")

    parsed = frame.copy()
    parsed["strategy"] = parsed["strategy"].map(lambda value: _as_text(value, "strategy"))
    try:
        for column in NUMERIC_SUMMARY_COLUMNS:
            parsed[column] = pd.to_numeric(parsed[column], errors="raise")
            parsed[column] = parsed[column].map(_as_float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path} has invalid numeric values") from exc
    return parsed


def _load_compare_equity(settings: Settings) -> pd.DataFrame:
    path = _latest_report_dir(settings.report_root) / "equity_curves.csv"
    return _load_date_indexed_csv(path)


def _resolve_strategy_ids(ids: list[str], summary_df: pd.DataFrame, strategy_columns: pd.Index) -> list[str]:
    columns = {str(column) for column in strategy_columns}
    alias_map = _build_alias_map(summary_df, columns)

    resolved: list[str] = []
    seen: set[str] = set()
    for run_id in ids:
        if run_id in columns:
            strategy = run_id
        elif run_id in ALIAS_IDS:
            strategy = alias_map.get(run_id)
        else:
            strategy = None

        if strategy and strategy not in seen:
            resolved.append(strategy)
            seen.add(strategy)
    return resolved


def _build_alias_map(summary_df: pd.DataFrame, strategy_columns: set[str]) -> dict[str, str]:
    eligible = summary_df[summary_df["strategy"].isin(strategy_columns)].copy()
    atlas_pool = eligible[~eligible["strategy"].str.startswith(BENCHMARK_PREFIXES)]
    momentum_pool = eligible[eligible["strategy"].str.startswith("TOP20_MOM_")]
    meanrev_pool = eligible[eligible["strategy"].str.startswith("TOP20_SECTOR_")]

    aliases: dict[str, str] = {}
    atlas = _pick_highest(atlas_pool, "sharpe")
    momentum = _pick_highest(momentum_pool, "cagr")
    meanrev = _pick_highest(meanrev_pool, "sharpe")
    if atlas is not None:
        aliases["atlas"] = atlas
    if momentum is not None:
        aliases["momentum"] = momentum
    if meanrev is not None:
        aliases["meanrev"] = meanrev
    return aliases


def _pick_highest(frame: pd.DataFrame, metric: str) -> str | None:
    if frame.empty:
        return None
    ranked = frame.assign(_metric=frame[metric].map(_as_float))
    ranked = ranked.sort_values(["_metric", "strategy"], ascending=[False, True])
    return str(ranked.iloc[0]["strategy"])


def _filter_equity_range(frame: pd.DataFrame, range_: str, settings: Settings) -> pd.DataFrame:
    if range_ not in VALID_RANGES:
        raise ValueError(f"Unsupported compare range: {range_}")
    if frame.empty:
        raise ValueError("equity_curves.csv has no rows for resolved compare ids")
    if range_ == "ALL":
        return frame

    anchor = _effective_anchor(frame.index, settings)
    if range_ == "YTD":
        start = pd.Timestamp(date(anchor.year, 1, 1))
    else:
        start = anchor - pd.Timedelta(days=RANGE_DAYS[range_])
    window = frame[(frame.index >= start) & (frame.index <= anchor)]
    if window.empty:
        raise ValueError(f"equity_curves.csv has no rows in range {range_}")
    return window


def _effective_anchor(index: pd.Index, settings: Settings) -> pd.Timestamp:
    anchor_date = settings.anchor_date or datetime.now(timezone.utc).date()
    anchor = pd.Timestamp(anchor_date)
    latest = pd.Timestamp(index.max()).normalize()
    if anchor > latest:
        return latest
    return anchor


def _downsample(frame: pd.DataFrame, *, max_points: int) -> pd.DataFrame:
    if len(frame) <= max_points:
        return frame
    step = (len(frame) - 1) / (max_points - 1)
    positions = sorted({round(index * step) for index in range(max_points)})
    positions[0] = 0
    positions[-1] = len(frame) - 1
    return frame.iloc[positions]


def _normalize(frame: pd.DataFrame, strategies: list[str]) -> pd.DataFrame:
    base = frame.iloc[0]
    for strategy in strategies:
        value = _as_float(base[strategy])
        if value <= 0:
            raise ValueError(f"Equity base must be positive for {strategy}")
    return frame.divide(base)


def _build_equity_points(frame: pd.DataFrame, strategies: list[str]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        points.append(
            {
                "ts": _date_string(index),
                "values": {strategy: _as_float(row[strategy]) for strategy in strategies},
            }
        )
    return points


def _build_metrics(summary_df: pd.DataFrame, strategies: list[str]) -> dict[str, dict[str, float]]:
    rows = summary_df.set_index("strategy", drop=False)
    missing = [strategy for strategy in strategies if strategy not in rows.index]
    if missing:
        raise ValueError(f"strategy_summary.csv missing metrics for: {', '.join(missing)}")

    metrics = {
        "cagr": "cagr",
        "sharpe": "sharpe",
        "sortino": "sortino",
        "max_dd": "max_drawdown",
        "calmar": "calmar",
        "win_rate": "monthly_win_rate",
        "avg_turnover": "annualized_turnover",
        "trades_per_year": "annualized_turnover",
    }
    return {
        metric_key: {strategy: _as_float(rows.loc[strategy, column]) for strategy in strategies}
        for metric_key, column in metrics.items()
    }


def _load_latest_universe(settings: Settings) -> list[str]:
    path = settings.data_root / "processed" / "rebalance_universe.csv"
    frame = _read_processed_csv(settings.data_root, "rebalance_universe.csv")
    required = {"symbol", "rebalance_date", "universe_rank"}
    missing = required - set(frame.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"{path} missing required columns: {missing_cols}")

    parsed = frame.copy()
    parsed["rebalance_date"] = pd.to_datetime(parsed["rebalance_date"], errors="coerce")
    if parsed["rebalance_date"].isna().any():
        raise ValueError(f"{path} has invalid dates in rebalance_date")
    try:
        parsed["universe_rank"] = pd.to_numeric(parsed["universe_rank"], errors="raise")
        parsed["universe_rank"] = parsed["universe_rank"].map(_as_float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path} has invalid numeric values in universe_rank") from exc

    latest_date = parsed["rebalance_date"].max()
    latest = parsed[parsed["rebalance_date"] == latest_date].sort_values(["universe_rank", "symbol"])
    symbols = [_as_text(value, "symbol") for value in latest["symbol"]]
    if not symbols:
        raise ValueError("rebalance_universe.csv has no latest universe symbols")
    return symbols


def _build_overlap(strategies: list[str], latest_universe: list[str]) -> dict[str, Any]:
    holdings = {strategy: _strategy_holdings(strategy, latest_universe) for strategy in strategies}
    matrix: list[list[float]] = []
    for left in strategies:
        row: list[float] = []
        for right in strategies:
            if left == right:
                row.append(1.0)
                continue
            union = holdings[left] | holdings[right]
            value = 0.0 if not union else len(holdings[left] & holdings[right]) / len(union)
            row.append(round(_as_float(value), 4))
        matrix.append(row)

    # This is a deterministic proxy: strategy names imply coarse holdings, not
    # per-run selections. TOP20/non-BH strategies use the latest top-20 universe;
    # BTC/ETH buy-and-hold rows are single-asset portfolios.
    shared_holdings = [
        {
            "symbol": symbol,
            "count": sum(1 for strategy in strategies if symbol in holdings[strategy]),
            "total": len(strategies),
        }
        for symbol in latest_universe[:3]
    ]
    return {"symbols": strategies, "matrix": matrix, "sharedHoldings": shared_holdings}


def _strategy_holdings(strategy: str, latest_universe: list[str]) -> set[str]:
    upper = strategy.upper()
    if upper.startswith("BTC_BH"):
        return {"BTC"}
    if upper.startswith("ETH_BH"):
        return {"ETH"}
    return set(latest_universe[:TOP_UNIVERSE_SIZE])


def _as_text(value: Any, column: str) -> str:
    if pd.isna(value):
        raise ValueError(f"Missing text value in {column}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Missing text value in {column}")
    return text
