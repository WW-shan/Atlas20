"""Overview payload adapter backed by report CSV artifacts."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from atlas20.api import mock_data
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
    mixed_source_fields = _build_aum_strategies_regime()
    anchor_date = settings.anchor_date or today()
    return {
        "champion": _build_champion(champion_row, champion_equity),
        "top_strategies": _build_top_strategies(summary_df),
        "equity_curve": _build_equity_curve(champion_equity),
        "daily_returns": _build_daily_returns(champion_daily_returns),
        "selection_history": mixed_source_fields["selection_history"],
        "aum": mixed_source_fields["aum"],
        "strategies": mixed_source_fields["strategies"],
        "regime": mixed_source_fields["regime"],
        "rebalance": _build_rebalance(daily_returns_df.index, champion_row),
        "equity_overlay": _build_equity_overlay(equity_curves_df, champion_col, anchor_date),
        "hero_kpi": _compute_hero_kpi(champion_daily_returns, champion_row, anchor_date),
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


def _build_champion(summary_row: pd.Series, equity_curve_col: pd.Series) -> dict[str, Any]:
    curve = equity_curve_col.dropna()
    if curve.empty:
        raise ValueError(f"Champion equity curve has no values: {summary_row['strategy']}")
    return {
        "strategy": str(summary_row["strategy"]),
        "window_start": _date_string(curve.index[0]),
        "window_end": _date_string(curve.index[-1]),
        "min_history_days": None,
        "min_daily_dollar_volume": None,
        "leader_pool": None,
        "rebalance_frequency": None,
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
    start = pd.Timestamp(date(anchor_date.year, 1, 1))
    end = pd.Timestamp(anchor_date)
    ytd = series[(series.index >= start) & (series.index <= end)]
    if ytd.empty:
        return {"series": [], "range": "YTD"}
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
    return {"series": points, "range": "YTD"}


def _build_rebalance(daily_returns_index: pd.Index, summary_row: pd.Series) -> dict[str, Any]:
    del summary_row
    if daily_returns_index.empty:
        raise ValueError("daily_returns.csv has no dates for rebalance timestamp")
    # TODO(P2): replace mock swaps with selection_history/weights-backed swaps.
    return {
        "ts": _date_string(daily_returns_index[-1]),
        "swaps": deepcopy(mock_data.fallback_overview["rebalance"]["swaps"]),
    }


def _build_aum_strategies_regime() -> dict[str, Any]:
    # TODO(P2): replace these half-mock fields when real AUM/strategy/regime sources exist.
    return {
        "selection_history": deepcopy(mock_data.fallback_overview["selection_history"]),
        "aum": deepcopy(mock_data.fallback_overview["aum"]),
        "strategies": deepcopy(mock_data.fallback_overview["strategies"]),
        "regime": deepcopy(mock_data.fallback_overview["regime"]),
    }


def _numeric_series(series: pd.Series, name: str) -> pd.Series:
    values = pd.to_numeric(series, errors="raise")
    values.name = name
    return values
