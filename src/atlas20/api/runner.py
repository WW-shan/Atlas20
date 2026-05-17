"""Constrained backtest runner used by the web API."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Iterable

import pandas as pd

from atlas20.analytics.metrics import compute_summary_metrics
from atlas20.api.schemas import BacktestRequest, RunStatus
from atlas20.backtest.engine import run_backtest
from atlas20.config import ResearchConfig, load_config
from atlas20.signals.regime import build_regime_frame
from atlas20.signals.risk import btc_above_trailing_price
from atlas20.strategies.momentum_lead import build_momentum_lead_targets
from atlas20.strategies.overlays import apply_daily_risk_overlay
from atlas20.universe.builder import MarketDataBundle, build_rebalance_universe, prepare_market_data

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "bear_bottom_to_current_2022_11_21_2026_04_22.yaml"
APP_RUNS_DIR = PROJECT_ROOT / "reports" / "app_runs"


def build_run_request_name(request: BacktestRequest) -> str:
    return (
        f"{request.strategy.family}_top{request.strategy.top_n}_"
        f"{request.strategy.frequency}_hist{request.universe.min_history_days}_"
        f"vol{request.universe.min_daily_dollar_volume:g}_"
        f"exbtc{int(request.universe.exclude_btc)}_"
        f"{request.risk.mode}_{request.risk.risk_off_asset}_"
        f"stop{request.risk.stop_lookback_days}_confirm{request.risk.confirm_days}_"
        f"win{request.window.start_date}_{request.window.end_date}_"
        f"w{request.weights.momentum_rank:.6f}-{request.weights.ret_21_rank:.6f}-"
        f"{request.weights.ret_42_rank:.6f}-{request.weights.near_high_rank:.6f}"
    )


def _request_digest(request: BacktestRequest) -> str:
    payload = request.model_dump_json()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _rows_to_frame(rows: Iterable[dict]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def write_run_artifacts(
    run_dir: Path,
    *,
    summary: dict,
    equity_rows: Iterable[dict],
    drawdown_rows: Iterable[dict],
    daily_return_rows: Iterable[dict],
    selection_rows: Iterable[dict],
    request: BacktestRequest | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([summary]).to_csv(run_dir / "summary.csv", index=False)
    _rows_to_frame(equity_rows).to_csv(run_dir / "equity_curve.csv", index=False)
    _rows_to_frame(drawdown_rows).to_csv(run_dir / "drawdowns.csv", index=False)
    _rows_to_frame(daily_return_rows).to_csv(run_dir / "daily_returns.csv", index=False)
    _rows_to_frame(selection_rows).to_csv(run_dir / "selection_history.csv", index=False)
    payload = request.model_dump(mode="json") if request else {}
    (run_dir / "request.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_processed_market(config: ResearchConfig, request: BacktestRequest) -> MarketDataBundle:
    processed_dir = config.resolve_path(config.paths.processed_dir)
    panel = pd.read_csv(processed_dir / "panel_daily.csv")
    metadata = pd.read_csv(processed_dir / "metadata.csv", index_col="coin_id")
    if request.universe.exclude_btc:
        panel = panel[panel["coin_id"] != "bitcoin"].copy()
        metadata = metadata.drop(index="bitcoin", errors="ignore")
    market = prepare_market_data(panel, metadata, config)
    start = pd.Timestamp(request.window.start_date)
    end = pd.Timestamp(request.window.end_date)
    return replace(
        market,
        raw_price=market.raw_price.loc[start:end],
        price=market.price.loc[start:end],
        returns=market.returns.loc[start:end],
        market_cap=market.market_cap.loc[start:end],
        volume=market.volume.loc[start:end],
        history_count=market.history_count.loc[start:end],
    )


def _configure_request(config: ResearchConfig, request: BacktestRequest) -> ResearchConfig:
    configured = config.model_copy(deep=True)
    configured.start_date = request.window.start_date
    configured.end_date = request.window.end_date
    configured.universe.min_history_days = request.universe.min_history_days
    configured.universe.min_daily_dollar_volume = request.universe.min_daily_dollar_volume
    return configured


def _risk_off_target(asset: str) -> pd.Series | None:
    if asset == "cash":
        return None
    return pd.Series({asset: 1.0})


def _series_rows(series: pd.Series, value_name: str) -> list[dict]:
    return [
        {"date": str(pd.Timestamp(date).date()), value_name: float(value)}
        for date, value in series.dropna().items()
    ]


def execute_backtest_request(request: BacktestRequest) -> RunStatus:
    config = _configure_request(load_config(DEFAULT_CONFIG_PATH), request)
    market = _load_processed_market(config, request)
    regime_frame = build_regime_frame(market.price, market.market_cap, config)
    rebalance_dates = pd.date_range(
        pd.Timestamp(request.window.start_date),
        pd.Timestamp(request.window.end_date),
        freq=request.strategy.frequency,
    )
    rebalance_dates = [pd.Timestamp(date) for date in rebalance_dates if date in market.price.index]
    universe = build_rebalance_universe(market, rebalance_dates, config)
    build_result = build_momentum_lead_targets(
        market,
        universe,
        regime_frame,
        config,
        top_n=request.strategy.top_n,
        frequency=request.strategy.frequency,
        regime_mode=request.risk.mode,
        weighted=request.strategy.top_n > 1,
        score_weights=request.weights.normalized(),
    )
    targets = build_result.targets
    if request.risk.stop_lookback_days > 0:
        risk_on = btc_above_trailing_price(
            market.price,
            lookback_days=request.risk.stop_lookback_days,
            confirm_days=request.risk.confirm_days,
        )
        parking_target = _risk_off_target(request.risk.risk_off_asset)
        targets = apply_daily_risk_overlay(
            targets,
            risk_on,
            immediate_reentry=True,
            risk_off_target=parking_target,
            initial_target=parking_target,
        )

    name = build_run_request_name(request)
    result = run_backtest(
        name=name,
        asset_returns=market.returns,
        rebalance_targets=targets,
        sector_by_coin=market.metadata["sector"],
        friction=config.frictions,
        initial_capital=config.initial_capital,
    )
    metrics = compute_summary_metrics(result, config.annualization_days)
    summary: dict[str, float | str | int | None] = {
        "strategy": name,
        "window_start": request.window.start_date,
        "window_end": request.window.end_date,
        "multiple": float(metrics["total_return"]) + 1.0,
        "ending_equity": float(result.equity_curve.iloc[-1]),
        **{key: float(value) for key, value in metrics.items()},
    }
    run_id = f"{_request_digest(request)}-{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}"
    run_dir = APP_RUNS_DIR / run_id
    selection_rows = build_result.selection_history.copy()
    if not selection_rows.empty:
        selection_rows["rebalance_date"] = pd.to_datetime(selection_rows["rebalance_date"]).dt.date.astype(str)
    write_run_artifacts(
        run_dir,
        summary=summary,
        equity_rows=_series_rows(result.equity_curve, "equity"),
        drawdown_rows=_series_rows(result.drawdown, "drawdown"),
        daily_return_rows=_series_rows(result.daily_returns, "daily_return"),
        selection_rows=selection_rows.to_dict(orient="records"),
        request=request,
    )
    return RunStatus(run_id=run_id, status="completed", name=name, summary=summary)
