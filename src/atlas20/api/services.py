"""Services for reading Atlas20 report artifacts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from atlas20.api.schemas import (
    ChampionResponse,
    OptionsResponse,
    OverviewResponse,
    SelectionHistoryRow,
    SeriesPoint,
    StrategySummary,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports" / "bear_bottom_to_current_2022_11_21_2026_04_22"
DEFAULT_CHAMPION_DIR = DEFAULT_REPORT_DIR / "profit_max_refine" / "champion_all_1m_14d_stop11_confirm2"


def _clean_record(record: dict) -> dict:
    return {str(key).lstrip("\ufeff"): value for key, value in record.items()}


def load_champion_summary(report_dir: Path = DEFAULT_CHAMPION_DIR) -> ChampionResponse:
    frame = pd.read_csv(report_dir / "champion_summary.csv")
    return ChampionResponse.model_validate(_clean_record(frame.iloc[0].to_dict()))


def load_top_strategies(report_dir: Path = DEFAULT_REPORT_DIR, limit: int = 10) -> list[StrategySummary]:
    frame = pd.read_csv(report_dir / "strategy_summary.csv")
    frame = frame.sort_values(["total_return", "sharpe"], ascending=[False, False]).head(limit)
    rows: list[StrategySummary] = []
    for _, row in frame.iterrows():
        rows.append(
            StrategySummary(
                strategy=str(row["strategy"]),
                multiple=float(row["total_return"]) + 1.0,
                cagr=float(row["cagr"]),
                sharpe=float(row["sharpe"]),
                max_drawdown=float(row["max_drawdown"]),
                annualized_turnover=float(row.get("annualized_turnover", 0.0)),
                monthly_win_rate=float(row.get("monthly_win_rate", 0.0)),
            )
        )
    return rows


def load_time_series(path: Path, value_column: str, limit: int | None = None) -> list[SeriesPoint]:
    frame = pd.read_csv(path)
    date_column = "date" if "date" in frame.columns else frame.columns[0]
    rows = frame[[date_column, value_column]].dropna()
    if limit:
        rows = rows.head(limit)
    return [
        SeriesPoint(date=str(pd.Timestamp(row[date_column]).date()), value=float(row[value_column]))
        for _, row in rows.iterrows()
    ]


def load_selection_history(path: Path, limit: int = 100) -> list[SelectionHistoryRow]:
    frame = pd.read_csv(path).tail(limit)
    rows: list[SelectionHistoryRow] = []
    for _, row in frame.iterrows():
        rows.append(
            SelectionHistoryRow(
                rebalance_date=str(pd.Timestamp(row["rebalance_date"]).date()),
                coin_id=str(row["coin_id"]),
                coin_rank=int(row["coin_rank"]),
                coin_score=float(row["coin_score"]) if pd.notna(row.get("coin_score")) else None,
                coin_weight=float(row["coin_weight"]),
            )
        )
    return rows


def get_overview_payload(
    report_dir: Path = DEFAULT_REPORT_DIR,
    champion_dir: Path = DEFAULT_CHAMPION_DIR,
) -> OverviewResponse:
    return OverviewResponse(
        champion=load_champion_summary(champion_dir),
        top_strategies=load_top_strategies(report_dir, limit=10),
        equity_curve=load_time_series(champion_dir / "equity_curve.csv", "equity"),
        daily_returns=load_time_series(champion_dir / "daily_returns.csv", "daily_return"),
        selection_history=load_selection_history(champion_dir / "selection_history.csv"),
    )


def get_options_payload() -> OptionsResponse:
    return OptionsResponse(
        strategy_families=["momentum_lead"],
        top_n_values=[1, 2, 3],
        frequencies=["7D", "14D"],
        risk_modes=["always_on", "bull_only"],
        risk_off_assets=["bitcoin", "ethereum", "cash"],
        min_history_days=[30, 60, 90],
        min_daily_dollar_volume=[1_000_000, 5_000_000, 10_000_000, 25_000_000],
    )
