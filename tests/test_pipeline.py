from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from atlas20.backtest.engine import BacktestResult
from atlas20.config import load_config
from atlas20 import pipeline


def _result(name: str, index: pd.DatetimeIndex) -> BacktestResult:
    daily_returns = pd.Series(0.0, index=index, name=name)
    equity_curve = pd.Series(100_000.0, index=index, name=name)
    drawdown = pd.Series(0.0, index=index, name=name)
    weights = pd.DataFrame({"bitcoin": 1.0}, index=index)
    turnover = pd.Series(0.0, index=index, name=name)
    holdings_count = pd.Series(1.0, index=index, name=name)
    sector_exposure = pd.DataFrame({"Store of Value": 1.0}, index=index)
    return BacktestResult(
        name=name,
        daily_returns=daily_returns,
        equity_curve=equity_curve,
        drawdown=drawdown,
        weights=weights,
        turnover=turnover,
        holdings_count=holdings_count,
        sector_exposure=sector_exposure,
        rebalance_targets=pd.DataFrame(),
    )


def test_run_research_pipeline_skips_sector_exposure_when_no_sector_strategy(tmp_path, monkeypatch):
    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    market = SimpleNamespace(
        price=pd.DataFrame({"bitcoin": [100.0, 101.0, 102.0]}, index=index),
        market_cap=pd.DataFrame({"bitcoin": [1_000.0, 1_010.0, 1_020.0]}, index=index),
        returns=pd.DataFrame({"bitcoin": [0.0, 0.01, 0.01]}, index=index),
    )
    metadata = {"sector": pd.Series({"bitcoin": "Store of Value"})}
    summary = pd.DataFrame(
        {"cagr": [0.1], "sharpe": [1.0], "max_drawdown": [-0.1]},
        index=pd.Index(["TOP20_MOM_alpha"], name="strategy"),
    )
    sector_plot_calls: list[object] = []

    monkeypatch.setattr(pipeline, "configure_logging", lambda level: None)
    monkeypatch.setattr(pipeline, "load_sector_config", lambda path: object())
    monkeypatch.setattr(pipeline, "download_and_cache_raw_data", lambda config: None)
    monkeypatch.setattr(pipeline, "build_processed_datasets", lambda config, sector_config: (object(), metadata))
    monkeypatch.setattr(pipeline, "prepare_market_data", lambda panel, metadata, config: market)
    monkeypatch.setattr(pipeline, "_all_rebalance_dates", lambda market_index, config: list(index))
    monkeypatch.setattr(pipeline, "build_rebalance_universe", lambda *args, **kwargs: object())
    monkeypatch.setattr(pipeline, "build_regime_frame", lambda price, market_cap, config: pd.DataFrame(index=index))
    monkeypatch.setattr(pipeline, "build_strategy_definitions", lambda config: [SimpleNamespace(name="TOP20_MOM_alpha")])
    monkeypatch.setattr(pipeline, "build_rebalance_targets", lambda strategy, market, universe, regime, config: ({}, None))
    monkeypatch.setattr(pipeline, "run_backtest", lambda name, **kwargs: _result(name, index))
    monkeypatch.setattr(pipeline, "summarize_backtests", lambda results, annualization_days: summary)
    monkeypatch.setattr(pipeline, "yearly_return_table", lambda results: pd.DataFrame())
    monkeypatch.setattr(pipeline, "performance_by_regime", lambda results, regime_frame, annualization_days: pd.DataFrame())
    monkeypatch.setattr(pipeline, "export_result_tables", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "plot_equity_curves", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "plot_drawdowns", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "plot_rolling_returns", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "plot_sector_exposure", lambda *args, **kwargs: sector_plot_calls.append(args))
    monkeypatch.setattr(pipeline, "build_markdown_report", lambda *args, **kwargs: "")

    results = pipeline.run_research_pipeline(config)

    assert set(results) == {"TOP20_MOM_alpha"}
    assert sector_plot_calls == []
