from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.analytics.metrics import compute_summary_metrics
from atlas20.backtest.engine import run_backtest
from atlas20.config import load_config, load_sector_config
from atlas20.data.processor import build_processed_datasets
from atlas20.logging_utils import configure_logging, ensure_dir
from atlas20.reporting.charts import plot_drawdowns, plot_equity_curves
from atlas20.reporting.report import dataframe_to_markdown
from atlas20.signals.regime import build_regime_frame
from atlas20.signals.risk import build_default_risk_overlays
from atlas20.strategies.implementations import build_rebalance_targets, build_strategy_definitions
from atlas20.strategies.overlays import apply_daily_risk_overlay
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data
from atlas20.backtest.calendar import get_rebalance_dates



def _all_rebalance_dates(index: pd.DatetimeIndex, config) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    for frequency_name, frequency_value in config.rebalancing.frequencies.items():
        dates.update(get_rebalance_dates(index, config.start_timestamp, frequency_name, frequency_value))
    return sorted(dates)



def main() -> None:
    parser = argparse.ArgumentParser(description='Run stop-loss overlay study for Atlas20.')
    parser.add_argument('--config', default='config/five_year_exact_2021_04_22_2026_04_22.yaml')
    parser.add_argument('--strategy', default='TOP20_MOM_top8_biweekly__bull_only')
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    sector_config = load_sector_config(config.resolve_path('config/sectors.yaml'))
    panel, metadata = build_processed_datasets(config, sector_config)
    market = prepare_market_data(panel, metadata, config)
    union_rebalance_dates = _all_rebalance_dates(market.price.index, config)
    universe = build_rebalance_universe(market, union_rebalance_dates, config)
    regime_frame = build_regime_frame(market.price, market.market_cap, config)
    strategy = {item.name: item for item in build_strategy_definitions(config)}[args.strategy]
    base_targets, _ = build_rebalance_targets(strategy, market, universe, regime_frame, config)
    sector_by_coin = metadata['sector']

    overlays = build_default_risk_overlays(market.price)
    results = {}
    rows = []
    report_dir = ensure_dir(config.resolve_path(config.paths.reports_dir) / 'stop_study')

    for overlay_name, (overlay_def, risk_on) in overlays.items():
        targets = apply_daily_risk_overlay(base_targets, risk_on)
        result_name = f'{strategy.name}__{overlay_name}'
        result = run_backtest(
            name=result_name,
            asset_returns=market.returns,
            rebalance_targets=targets,
            sector_by_coin=sector_by_coin,
            friction=config.frictions,
            initial_capital=config.initial_capital,
        )
        results[result_name] = result
        metrics = compute_summary_metrics(result, config.annualization_days)
        metrics.update(
            {
                'strategy': result_name,
                'overlay': overlay_name,
                'description': overlay_def.description,
                'risk_on_fraction': float(risk_on.mean()),
            }
        )
        rows.append(metrics)

    summary = pd.DataFrame(rows).set_index('strategy').sort_values(['sharpe', 'cagr'], ascending=False)
    summary.to_csv(report_dir / 'stop_study_summary.csv')
    pd.DataFrame({name: result.daily_returns for name, result in results.items()}).to_csv(report_dir / 'stop_study_daily_returns.csv')
    pd.DataFrame({name: result.equity_curve for name, result in results.items()}).to_csv(report_dir / 'stop_study_equity_curves.csv')
    pd.DataFrame({name: result.drawdown for name, result in results.items()}).to_csv(report_dir / 'stop_study_drawdowns.csv')

    plot_equity_curves(results, report_dir / 'stop_study_equity_curves.png')
    plot_drawdowns(results, report_dir / 'stop_study_drawdowns.png')

    markdown_lines = [
        f'# Stop-Loss Study - {strategy.name}',
        '',
        f'Window: {config.start_date} to {config.end_date}',
        '',
        '## Overlay Summary',
        '',
        dataframe_to_markdown(
            summary[['overlay', 'description', 'cagr', 'sharpe', 'max_drawdown', 'annualized_turnover', 'risk_on_fraction']],
            percent_columns={'cagr', 'max_drawdown', 'risk_on_fraction'},
            number_columns={'sharpe', 'annualized_turnover'},
        ),
        '',
        '## Notes',
        '',
        '- Market-based stop overlays trigger on daily BTC data and exit the portfolio on the next trading day.',
        '- Re-entry occurs on the next scheduled rebalance date once the overlay condition is risk-on again.',
        '- This study isolates stop overlays on one strategy, rather than applying them to the full strategy grid.',
    ]
    (report_dir / 'stop_study_report.md').write_text('\n'.join(markdown_lines), encoding='utf-8')


if __name__ == '__main__':
    main()
