"""Overview payload adapter backed by report CSV artifacts."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from atlas20.api._time import today
from atlas20.api.data_access._common import _as_float, _date_string, _latest_report_dir, _load_date_indexed_csv, _read_csv
from atlas20.api.settings import Settings


SUMMARY_COLUMNS = {
    "strategy",
    "total_return",
    "cagr",
    "sharpe",
    "max_drawdown",
    "monthly_win_rate",
    "annualized_turnover",
}
BTC_BENCHMARK = "BTC_BH__always_on"


def load_overview_from_reports(settings: Settings) -> dict[str, Any]:
    """Build OverviewPayload from report CSVs."""
    summary_df = _load_strategy_summary(settings.report_root)
    equity_curves_df = _load_equity_curves(settings.report_root)
    daily_returns_df = _load_daily_returns(settings.report_root)

    champion_row = _pick_champion(summary_df)
    champion_col = str(champion_row["strategy"])
    if champion_col not in equity_curves_df.columns:
        raise ValueError(f"Missing champion column in equity_curves.csv: {champion_col}")
    if champion_col not in daily_returns_df.columns:
        raise ValueError(f"Missing champion column in daily_returns.csv: {champion_col}")

    champion_equity = _numeric_series(equity_curves_df[champion_col], champion_col)
    champion_daily_returns = _numeric_series(daily_returns_df[champion_col], champion_col)
    selection_history = _load_selection_history(settings.report_root)
    anchor_date = settings.anchor_date or today()
    return {
        "champion": _build_champion(champion_row, champion_equity, selection_history),
        "top_strategies": _build_top_strategies(summary_df),
        "equity_curve": _build_equity_curve(champion_equity),
        "daily_returns": _build_daily_returns(champion_daily_returns),
        "selection_history": _build_selection_history_payload(selection_history),
        "aum": _build_aum(summary_df, equity_curves_df, champion_equity),
        "strategies": _build_strategies_breakdown(summary_df),
        "regime": _build_regime(settings),
        "rebalance": _build_rebalance(daily_returns_df.index, champion_row, selection_history),
        "equity_overlay": _build_equity_overlay(equity_curves_df, champion_col, anchor_date),
        "hero_kpi": _compute_hero_kpi(champion_daily_returns, champion_row, anchor_date),
        "last_sync_seconds": _compute_last_sync_seconds(settings.report_root),
    }


def _load_strategy_summary(report_root: Path) -> pd.DataFrame:
    path = _latest_report_dir(report_root) / "strategy_summary.csv"
    frame = _read_csv(path)
    missing = SUMMARY_COLUMNS - set(frame.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"{path} missing required columns: {missing_cols}")
    frame = frame.copy()
    for column in SUMMARY_COLUMNS - {"strategy"}:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    return frame


def _load_equity_curves(report_root: Path) -> pd.DataFrame:
    path = _latest_report_dir(report_root) / "equity_curves.csv"
    return _load_date_indexed_csv(path)


def _load_daily_returns(report_root: Path) -> pd.DataFrame:
    path = _latest_report_dir(report_root) / "daily_returns.csv"
    return _load_date_indexed_csv(path)


def _pick_champion(summary_df: pd.DataFrame) -> pd.Series:
    eligible = summary_df[summary_df["strategy"] != BTC_BENCHMARK]
    ranked = eligible if not eligible.empty else summary_df
    return ranked.sort_values("sharpe", ascending=False).iloc[0]


def _build_top_strategies(summary_df: pd.DataFrame, n: int = 3) -> list[dict[str, Any]]:
    rows = summary_df.sort_values("sharpe", ascending=False).head(n)
    return [_strategy_summary_from_row(row) for _, row in rows.iterrows()]


def _strategy_summary_from_row(row: pd.Series) -> dict[str, Any]:
    return {
        "strategy": str(row["strategy"]),
        "multiple": _as_float(row["total_return"]) + 1.0,
        "cagr": _as_float(row["cagr"]),
        "sharpe": _as_float(row["sharpe"]),
        "max_drawdown": _as_float(row["max_drawdown"]),
        "annualized_turnover": _as_float(row["annualized_turnover"]),
        "monthly_win_rate": _as_float(row["monthly_win_rate"]),
    }


def _build_champion(
    summary_row: pd.Series,
    equity_curve_col: pd.Series,
    selection_history: pd.DataFrame | None,
) -> dict[str, Any]:
    curve = equity_curve_col.dropna()
    if curve.empty:
        raise ValueError(f"Champion equity curve has no values: {summary_row['strategy']}")
    strategy = str(summary_row["strategy"])
    return {
        "strategy": strategy,
        "display_name": _format_display_name(strategy),
        "window_start": _date_string(curve.index[0]),
        "window_end": _date_string(curve.index[-1]),
        "min_history_days": None,
        "min_daily_dollar_volume": None,
        "leader_pool": None,
        "rebalance_frequency": _parse_cadence(strategy, selection_history),
        "regime_mode": None,
        "risk_off_asset": None,
        "initial_asset": None,
        "btc_stop_lookback_days": None,
        "btc_stop_confirm_days": None,
        "weight_momentum_rank": None,
        "weight_ret_21_rank": None,
        "weight_ret_42_rank": None,
        "weight_near_high_rank": None,
        "multiple": _as_float(summary_row["total_return"]) + 1.0,
        "total_return": _as_float(summary_row["total_return"]),
        "cagr": _as_float(summary_row["cagr"]),
        "sharpe": _as_float(summary_row["sharpe"]),
        "max_drawdown": _as_float(summary_row["max_drawdown"]),
        "annualized_turnover": _as_float(summary_row["annualized_turnover"]),
        "monthly_win_rate": _as_float(summary_row["monthly_win_rate"]),
        "ending_equity": _as_float(curve.iloc[-1]),
    }


def _compute_ytd_return(daily_returns_col: pd.Series, anchor_date: date) -> float:
    window = _ytd_returns_window(daily_returns_col, anchor_date)
    if window.empty:
        return 0.0
    return _as_float((1.0 + window).prod() - 1.0)


def _compute_hero_kpi(daily_returns_col: pd.Series, summary_row: pd.Series, anchor_date: date) -> dict[str, float]:
    window = _ytd_returns_window(daily_returns_col, anchor_date)
    win_rate = 0.0 if window.empty else _as_float((window > 0).sum() / len(window))
    return {
        "ytdReturn": _compute_ytd_return(daily_returns_col, anchor_date),
        "sharpe": _as_float(summary_row["sharpe"]),
        "maxDd": _as_float(summary_row["max_drawdown"]),
        "winRate": win_rate,
    }


def _ytd_returns_window(daily_returns_col: pd.Series, anchor_date: date) -> pd.Series:
    series = _numeric_series(daily_returns_col, daily_returns_col.name or "daily_returns").dropna()
    start = pd.Timestamp(date(anchor_date.year, 1, 1))
    end = pd.Timestamp(anchor_date)
    return series[(series.index >= start) & (series.index <= end)]


def _build_equity_curve(equity_curves_col: pd.Series) -> list[dict[str, Any]]:
    monthly = _numeric_series(equity_curves_col, equity_curves_col.name or "equity").resample("ME").last().dropna()
    return [{"date": _date_string(index), "value": _as_float(value)} for index, value in monthly.tail(6).items()]


def _build_daily_returns(daily_returns_col: pd.Series) -> list[dict[str, Any]]:
    monthly = (1.0 + _numeric_series(daily_returns_col, daily_returns_col.name or "returns")).resample("ME").prod() - 1.0
    return [{"date": _date_string(index), "value": _as_float(value)} for index, value in monthly.dropna().tail(6).items()]


def _build_equity_overlay(equity_curves_df: pd.DataFrame, champion_col: str, anchor_date: date) -> dict[str, Any]:
    if BTC_BENCHMARK not in equity_curves_df.columns:
        raise ValueError(f"Missing benchmark column in equity_curves.csv: {BTC_BENCHMARK}")
    series = pd.concat(
        {
            "atlas": _numeric_series(equity_curves_df[champion_col], champion_col),
            "btc": _numeric_series(equity_curves_df[BTC_BENCHMARK], BTC_BENCHMARK),
        },
        axis=1,
    ).dropna()
    if series.empty:
        raise ValueError("equity_curves.csv has no overlapping atlas+btc data")
    start = pd.Timestamp(date(anchor_date.year, 1, 1))
    end = pd.Timestamp(anchor_date)
    ytd = series[(series.index >= start) & (series.index <= end)]
    if ytd.empty:
        ytd = series
        range_label = "ALL"
    else:
        range_label = "YTD"
    base = ytd.iloc[0]
    if not pd.Series([base["atlas"], base["btc"]]).map(pd.notna).all() or (base["atlas"] <= 0) or (base["btc"] <= 0):
        raise ValueError("Equity overlay base values must be positive")
    monthly = ytd.resample("ME").last().dropna()
    points = [
        {
            "ts": index.strftime("%b %Y"),
            "atlas": _as_float(((row["atlas"] / base["atlas"]) - 1.0) * 100.0),
            "btc": _as_float(((row["btc"] / base["btc"]) - 1.0) * 100.0),
        }
        for index, row in monthly.iterrows()
    ]
    return {
        "series": points,
        "range": range_label,
        "atlas_label": _format_display_name(champion_col),
        "btc_label": "BTC Benchmark",
    }


def _build_rebalance(
    daily_returns_index: pd.Index,
    summary_row: pd.Series,
    selection_history: pd.DataFrame | None,
) -> dict[str, Any]:
    if daily_returns_index.empty:
        raise ValueError("daily_returns.csv has no dates for rebalance timestamp")
    strategy = str(summary_row["strategy"])
    swaps = _compute_rebalance_swaps(selection_history, strategy)
    return {
        "ts": _date_string(daily_returns_index[-1]),
        "swaps": swaps,
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
    family = _strategy_family(strategy)
    for prefix, _ in _STRATEGY_FAMILY_PREFIXES:
        if strategy.startswith(prefix):
            variant = strategy[len(prefix):].lstrip("_")
            if not variant:
                return family
            cleaned = variant.replace("__", " · ").replace("_", " ")
            return f"{family} · {cleaned.title()}"
    return strategy.replace("__", " · ").replace("_", " ").title()


def _parse_cadence(strategy: str, selection_history: pd.DataFrame | None) -> str | None:
    strategy_lower = strategy.lower()
    for token, label in [
        ("_biweekly_", "Biweekly"),
        ("_weekly_", "Weekly"),
        ("_monthly_", "Monthly"),
        ("_14d_", "Biweekly"),
        ("_7d_", "Weekly"),
        ("_30d_", "Monthly"),
    ]:
        if token in strategy_lower:
            return label
    if selection_history is None or selection_history.empty:
        return None
    if "strategy" not in selection_history.columns or "rebalance_date" not in selection_history.columns:
        return None
    scope = selection_history[selection_history["strategy"].astype(str) == strategy]
    if scope.empty:
        return None
    dates = pd.to_datetime(scope["rebalance_date"], errors="coerce").dropna().drop_duplicates().sort_values()
    if len(dates) < 2:
        return None
    diffs = dates.diff().dropna().dt.days
    if diffs.empty:
        return None
    median_days = int(round(float(diffs.median())))
    if median_days <= 8:
        return "Weekly"
    if median_days <= 21:
        return "Biweekly"
    if median_days <= 45:
        return "Monthly"
    return f"{median_days}D"


def _compute_last_sync_seconds(report_root: Path) -> int:
    try:
        target_dir = _latest_report_dir(report_root)
        return max(0, int(time.time() - target_dir.stat().st_mtime))
    except (FileNotFoundError, ValueError):
        return 0


def _build_strategies_breakdown(summary_df: pd.DataFrame) -> dict[str, Any]:
    """Group all completed strategies in strategy_summary.csv by family prefix."""
    families: dict[str, int] = {}
    for name in summary_df["strategy"].astype(str):
        family = _strategy_family(name)
        families[family] = families.get(family, 0) + 1
    # Stable order: by descending count, then alphabetical for tie-break.
    ordered = sorted(families.items(), key=lambda item: (-item[1], item[0]))
    return {
        "total": int(sum(families.values())),
        "breakdown": [{"family": family, "count": count} for family, count in ordered],
    }


def _build_aum(
    summary_df: pd.DataFrame,
    equity_curves_df: pd.DataFrame,
    champion_equity: pd.Series,
) -> dict[str, Any]:
    """Research-only "tracked notional" total surfaced through the AUM schema slot.

    Atlas20 is a research console — there is no real production AUM. The
    OverviewPayload.aum schema is reused here to expose a "tracked notional"
    figure with a defensible interpretation: SUM across every strategy in
    strategy_summary.csv of that strategy's most recent equity-curve value.
    Each backtest is run from the same config.initial_capital starting
    point, so the sum answers: "if you had simulated $initial_capital on
    every strategy independently, what's the combined notional now?"

    - `current`: sum of final equity values across all tracked strategies.
    - `sparkline`: champion equity tail (14 samples) as a representative
      shape; the per-strategy sum would average out interesting movement,
      while the champion's trajectory is what the user is tracking anyway.
    - `deltaPct`: relative move across the champion sparkline window.

    The UI labels this "TRACKED NOTIONAL · RESEARCH" so a reader does not
    confuse it with production AUM (which would require broker / custody
    integration that Atlas20 does not have).
    """
    tracked_strategies = [
        column
        for column in equity_curves_df.columns
        if column in set(summary_df["strategy"].astype(str))
    ]
    if not tracked_strategies:
        current = 0.0
    else:
        latest_row = equity_curves_df[tracked_strategies].dropna(how="all").iloc[-1]
        current = float(latest_row.fillna(0.0).sum())
    if champion_equity.empty:
        return {"current": current, "deltaPct": 0.0, "sparkline": []}
    spark_window = champion_equity.iloc[-14:]
    sparkline = [float(v) for v in spark_window.tolist()]
    if len(sparkline) >= 2:
        first = sparkline[0] or 1.0
        delta_pct = (sparkline[-1] - first) / first
    else:
        delta_pct = 0.0
    return {
        "current": current,
        "deltaPct": delta_pct,
        "sparkline": sparkline,
    }


def _build_regime(settings: Settings) -> dict[str, Any]:
    """Read the regime label from the latest processed dataset's regime_frame.csv.

    The pipeline writes regime_frame.csv next to its processed parquet/csv
    output for every preset. Atlas20's research console doesn't have a
    "current" regime per-strategy, so we pick the dataset whose regime_frame
    has the most recent row and use that as the global market regime.

    Searches both `data/processed/regime_frame.csv` (used by base/default
    preset runs that don't carve out a preset subdir) and
    `data/processed/<preset>/regime_frame.csv` (preset-specific runs).
    """
    processed_root = settings.data_root / "processed"
    candidates = sorted(processed_root.glob("*/regime_frame.csv"))
    root_candidate = processed_root / "regime_frame.csv"
    if root_candidate.exists():
        candidates.append(root_candidate)
    fallback = {
        "label": "NEUTRAL",
        "score": 0.5,
        "model": "regime_frame.csv unavailable",
    }
    if not candidates:
        return fallback
    best: tuple[pd.Timestamp, pd.DataFrame] | None = None
    for candidate in candidates:
        try:
            frame = pd.read_csv(candidate, index_col=0, parse_dates=True)
        except (FileNotFoundError, pd.errors.EmptyDataError, ValueError):
            continue
        if frame.empty:
            continue
        # frame.index.max() handles unsorted files; iloc[-1] would silently
        # pick the wrong row when the pipeline rebuilds and rewrites in
        # different ordering.
        latest_ts = frame.index.max()
        if best is None or latest_ts > best[0]:
            best = (latest_ts, frame)
    if best is None:
        return fallback
    latest_ts, frame = best
    last_row = frame.loc[latest_ts] if latest_ts in frame.index else frame.iloc[-1]
    if isinstance(last_row, pd.DataFrame):  # duplicate timestamp -> pick last
        last_row = last_row.iloc[-1]
    bull = bool(last_row.get("bull", False))
    btc_above = bool(last_row.get("btc_above_ma", False))
    mcap_above = bool(last_row.get("tracked_total_mcap_above_ma", False))
    # Score = fraction of regime indicators currently in bull state.
    score = float(sum([bull, btc_above, mcap_above]) / 3.0)
    if bull and btc_above and mcap_above:
        label = "RISK-ON"
    elif not bull and not btc_above and not mcap_above:
        label = "RISK-OFF"
    else:
        label = "NEUTRAL"
    return {"label": label, "score": score, "model": "bull AND btc>MA200 AND mcap>MA200"}


def _build_selection_history_payload(
    selection_history: pd.DataFrame | None,
) -> list[dict[str, Any]]:
    if selection_history is None or selection_history.empty:
        return []
    latest_date = selection_history["rebalance_date"].max()
    latest = selection_history[selection_history["rebalance_date"] == latest_date].copy()
    latest = latest.sort_values("coin_rank")
    return [
        {
            "rebalance_date": str(row["rebalance_date"]),
            "coin_id": str(row["coin_id"]),
            "coin_rank": int(row["coin_rank"]),
            "coin_score": float(row["coin_score"]) if pd.notna(row.get("coin_score")) else None,
            "coin_weight": float(row["coin_weight"]),
        }
        for _, row in latest.iterrows()
    ]


def _load_selection_history(report_root: Path) -> pd.DataFrame | None:
    path = _latest_report_dir(report_root) / "selection_history.csv"
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, ValueError):
        return None


def _compute_rebalance_swaps(
    selection_history: pd.DataFrame | None,
    strategy: str,
) -> list[dict[str, Any]]:
    """Diff the last two rebalance dates → IN/OUT swaps.

    The Overview rebalance panel is meaningful only for strategies that
    actually rotate. If the champion is a buy-and-hold benchmark (single
    coin held forever) we'd show "no swaps" which is technically correct
    but useless to the user. Fall through to the first rotation strategy
    (TOP20_MOM_* / TOP20_SECTOR_*) when the champion has no swap activity.
    """
    if selection_history is None or selection_history.empty:
        return []
    candidates: list[str] = [strategy]
    rotation_pool = sorted(
        s
        for s in selection_history["strategy"].astype(str).unique()
        if s.startswith(("TOP20_MOM", "TOP20_SECTOR"))
    )
    candidates.extend(s for s in rotation_pool if s not in candidates)
    for candidate in candidates:
        swaps = _strategy_swaps(selection_history, candidate)
        if swaps:
            return swaps
    return []


def _strategy_swaps(selection_history: pd.DataFrame, strategy: str) -> list[dict[str, Any]]:
    scope = selection_history[selection_history["strategy"] == strategy]
    if scope.empty:
        return []
    dates = sorted(scope["rebalance_date"].unique())
    if len(dates) < 2:
        return []
    prev_set = set(scope[scope["rebalance_date"] == dates[-2]]["coin_id"])
    curr_rows = scope[scope["rebalance_date"] == dates[-1]]
    curr_set = set(curr_rows["coin_id"])
    out_coins = sorted(prev_set - curr_set)
    in_coins = sorted(curr_set - prev_set)
    weight_by_coin = {
        str(row["coin_id"]): float(row.get("coin_weight", 0.0) or 0.0)
        for _, row in curr_rows.iterrows()
    }
    swaps: list[dict[str, Any]] = []
    for out_coin, in_coin in zip(out_coins, in_coins):
        delta_pct = weight_by_coin.get(in_coin, 0.0)
        swaps.append({"out": out_coin.upper(), "in": in_coin.upper(), "deltaPct": delta_pct})
    return swaps


def _numeric_series(series: pd.Series, name: str) -> pd.Series:
    values = pd.to_numeric(series, errors="raise")
    values.name = name
    return values
