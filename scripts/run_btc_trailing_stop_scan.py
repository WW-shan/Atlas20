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
from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.backtest.engine import run_backtest
from atlas20.config import load_config, load_sector_config
from atlas20.data.processor import build_processed_datasets
from atlas20.logging_utils import configure_logging, ensure_dir
from atlas20.reporting.charts import plot_drawdowns, plot_equity_curves
from atlas20.reporting.report import dataframe_to_markdown
from atlas20.signals.regime import build_regime_frame
from atlas20.signals.risk import btc_above_moving_average, btc_above_trailing_price
from atlas20.strategies.implementations import build_rebalance_targets, build_strategy_definitions
from atlas20.strategies.overlays import apply_daily_risk_overlay
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data
from atlas20.utils import slugify


def _all_rebalance_dates(index: pd.DatetimeIndex, config) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    for frequency_name, frequency_value in config.rebalancing.frequencies.items():
        dates.update(get_rebalance_dates(index, config.start_timestamp, frequency_name, frequency_value))
    return sorted(dates)


def main() -> None:
    parser = argparse.ArgumentParser(description='Run BTC trailing-stop parameter scan for Atlas20.')
    parser.add_argument('--config', default='config/five_year_exact_2021_04_22_2026_04_22.yaml')
    parser.add_argument('--strategy', default='TOP20_MOM_top8_biweekly__bull_only')
    parser.add_argument('--lookbacks', nargs='*', type=int, default=[10, 14, 21, 28])
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

    overlays: list[tuple[str, str, pd.Series]] = [
        ('NO_STOP', 'No additional stop-loss overlay.', pd.Series(True, index=market.price.index, name='no_stop')),
    ]
    for lookback in args.lookbacks:
        overlays.append(
            (
                f'BTC_LT_{lookback}D',
                f'Exit to cash when BTC closes below its level {lookback} days earlier; re-enter at next rebalance once the condition clears.',
                btc_above_trailing_price(market.price, lookback_days=lookback, confirm_days=1),
            )
        )
    overlays.append(
        (
            'BTC_LT_20DMA',
            'Exit to cash when BTC closes below its 20-day moving average; re-enter at next rebalance once back above.',
            btc_above_moving_average(market.price, ma_window=20, confirm_days=1),
        )
    )

    report_dir = ensure_dir(config.resolve_path(config.paths.reports_dir) / 'stop_scan_trailing' / slugify(args.strategy))
    results = {}
    rows = []

    for overlay_name, description, risk_on in overlays:
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
                'description': description,
                'risk_on_fraction': float(risk_on.mean()),
            }
        )
        rows.append(metrics)

    summary = pd.DataFrame(rows).set_index('strategy')
    summary['drawdown_improvement_vs_no_stop'] = summary['max_drawdown'] - summary.loc[f'{strategy.name}__NO_STOP', 'max_drawdown']
    summary['cagr_delta_vs_no_stop'] = summary['cagr'] - summary.loc[f'{strategy.name}__NO_STOP', 'cagr']
    summary = summary.sort_values(['sharpe', 'cagr'], ascending=False)
    summary.to_csv(report_dir / 'trailing_stop_scan_summary.csv')
    pd.DataFrame({name: result.daily_returns for name, result in results.items()}).to_csv(report_dir / 'trailing_stop_scan_daily_returns.csv')
    pd.DataFrame({name: result.equity_curve for name, result in results.items()}).to_csv(report_dir / 'trailing_stop_scan_equity_curves.csv')
    pd.DataFrame({name: result.drawdown for name, result in results.items()}).to_csv(report_dir / 'trailing_stop_scan_drawdowns.csv')

    plot_equity_curves(results, report_dir / 'trailing_stop_scan_equity_curves.png')
    plot_drawdowns(results, report_dir / 'trailing_stop_scan_drawdowns.png')

    markdown_lines = [
        f'# BTC Trailing Stop Scan - {strategy.name}',
        '',
        f'Window: {config.start_date} to {config.end_date}',
        '',
        '## Summary',
        '',
        dataframe_to_markdown(
            summary[[
                'overlay', 'cagr', 'sharpe', 'max_drawdown', 'annualized_turnover',
                'risk_on_fraction', 'cagr_delta_vs_no_stop', 'drawdown_improvement_vs_no_stop',
            ]],
            percent_columns={'cagr', 'max_drawdown', 'risk_on_fraction', 'cagr_delta_vs_no_stop', 'drawdown_improvement_vs_no_stop'},
            number_columns={'sharpe', 'annualized_turnover'},
        ),
        '',
        '## Notes',
        '',
        '- Daily BTC stop signals trigger exits on the next trading day.',
        '- Re-entry happens at the next scheduled rebalance once BTC is back in risk-on mode.',
        '- Positive `drawdown_improvement_vs_no_stop` means a shallower drawdown than the no-stop baseline.',
    ]
    (report_dir / 'trailing_stop_scan_report.md').write_text('\n'.join(markdown_lines), encoding='utf-8')


if __name__ == '__main__':
    main()
