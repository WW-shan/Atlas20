"""End-to-end Atlas20 research pipeline."""

from __future__ import annotations

import pandas as pd

from atlas20.analytics.metrics import performance_by_regime, summarize_backtests, yearly_return_table
from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.backtest.engine import BacktestResult, run_backtest
from atlas20.config import ResearchConfig, load_sector_config
from atlas20.data.processor import build_processed_datasets, download_and_cache_raw_data
from atlas20.logging_utils import configure_logging, ensure_dir, get_logger
from atlas20.reporting.charts import plot_drawdowns, plot_equity_curves, plot_rolling_returns, plot_sector_exposure
from atlas20.reporting.report import build_markdown_report, export_result_tables
from atlas20.signals.regime import build_regime_frame
from atlas20.strategies.implementations import build_rebalance_targets, build_strategy_definitions
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data

LOGGER = get_logger(__name__)



def _all_rebalance_dates(market_index: pd.DatetimeIndex, config: ResearchConfig) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    for frequency_name, frequency_value in config.rebalancing.frequencies.items():
        dates.update(get_rebalance_dates(market_index, config.start_timestamp, frequency_name, frequency_value))
    return sorted(dates)



def run_research_pipeline(config: ResearchConfig, refresh_raw: bool = False) -> dict[str, BacktestResult]:
    """Run the full Atlas20 workflow and write report artifacts."""
    configure_logging(config.logging.level)
    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    reports_dir = ensure_dir(config.resolve_path(config.paths.reports_dir))
    processed_dir = ensure_dir(config.resolve_path(config.paths.processed_dir))
    candidate_cache = config.resolve_path(config.paths.raw_dir) / "coingecko" / "candidate_assets.json"

    if refresh_raw or not candidate_cache.exists():
        LOGGER.info("Stage 1/5 - Downloading raw data")
        download_and_cache_raw_data(config)
    else:
        LOGGER.info("Stage 1/5 - Using cached raw data (pass refresh_raw=True to update)")

    LOGGER.info("Stage 2/5 - Building processed datasets")
    panel, metadata = build_processed_datasets(config, sector_config)
    market = prepare_market_data(panel, metadata, config)

    LOGGER.info("Stage 3/5 - Building historical universe and regime filter")
    union_rebalance_dates = _all_rebalance_dates(market.price.index, config)
    universe = build_rebalance_universe(
        market,
        union_rebalance_dates,
        config,
        output_path=processed_dir / "rebalance_universe.csv",
    )
    regime_frame = build_regime_frame(market.price, market.market_cap, config)
    regime_frame.to_csv(processed_dir / "regime_frame.csv")

    LOGGER.info("Stage 4/5 - Running strategy backtests")
    strategy_definitions = build_strategy_definitions(config)
    results: dict[str, BacktestResult] = {}
    sector_by_coin = metadata["sector"]
    # market.returns extends back by min_history_days for universe eligibility
    # (see processor.py and dd3bfba). The backtest itself must run only on
    # [start_timestamp, end_timestamp]; otherwise daily_returns picks up the
    # pre-window buffer rows (all zero), which dilutes CAGR / sharpe and skews
    # yearly_return_table / regime_perf in analytics. Universe builder and
    # regime detection still see the full panel.
    backtest_returns = market.returns.loc[config.start_timestamp : config.end_timestamp]

    for strategy in strategy_definitions:
        targets, _ = build_rebalance_targets(strategy, market, universe, regime_frame, config)
        result = run_backtest(
            name=strategy.name,
            asset_returns=backtest_returns,
            rebalance_targets=targets,
            sector_by_coin=sector_by_coin,
            friction=config.frictions,
            initial_capital=config.initial_capital,
        )
        results[strategy.name] = result

    LOGGER.info("Stage 5/5 - Analytics and reporting")
    summary = summarize_backtests(results, config.annualization_days)
    yearly = yearly_return_table(results)
    regime_perf = performance_by_regime(results, regime_frame, config.annualization_days)
    export_result_tables(results, summary, yearly, regime_perf, reports_dir)

    selected = config.reporting.selected_strategies_for_plots
    plot_equity_curves(results, reports_dir / "equity_curves.png", selected=selected)
    plot_drawdowns(results, reports_dir / "drawdowns.png", selected=selected)
    plot_rolling_returns(results, reports_dir / "rolling_12m_returns.png", config.reporting.rolling_window_days, selected=selected)

    best_sector_name = summary[summary.index.to_series().str.startswith("TOP20_SECTOR_")].index[0]
    best_sector_exposure = results[best_sector_name].sector_exposure
    best_sector_exposure.to_csv(reports_dir / f"sector_exposure_{best_sector_name}.csv")
    plot_sector_exposure(
        best_sector_exposure,
        reports_dir / f"sector_exposure_{best_sector_name}.png",
        title=f"Sector Exposure - {best_sector_name}",
    )

    build_markdown_report(config, summary, yearly, regime_perf, reports_dir / "atlas20_report.md")
    LOGGER.info("Pipeline complete. Report directory: %s", reports_dir)
    return results
