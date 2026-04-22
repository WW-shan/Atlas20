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
from atlas20.signals.risk import btc_above_trailing_price
from atlas20.strategies.implementations import build_rebalance_targets, build_strategy_definitions
from atlas20.strategies.overlays import apply_daily_risk_overlay
from atlas20.strategies.sector_lead_v3 import build_sector_lead_v3_targets
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data



def _all_rebalance_dates(index: pd.DatetimeIndex, config) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    for frequency_name, frequency_value in config.rebalancing.frequencies.items():
        dates.update(get_rebalance_dates(index, config.start_timestamp, frequency_name, frequency_value))
    return sorted(dates)



def main() -> None:
    parser = argparse.ArgumentParser(description='Run Sector-Lead V3 parameter scan.')
    parser.add_argument('--config', default='config/five_year_exact_2021_04_22_2026_04_22.yaml')
    parser.add_argument('--lookbacks', nargs='*', type=int, default=[14, 18, 21, 24])
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    sector_config = load_sector_config(config.resolve_path('config/sectors.yaml'))
    panel, metadata = build_processed_datasets(config, sector_config)
    market = prepare_market_data(panel, metadata, config)
    union_rebalance_dates = _all_rebalance_dates(market.price.index, config)
    universe = build_rebalance_universe(market, union_rebalance_dates, config)
    regime_frame = build_regime_frame(market.price, market.market_cap, config)
    sector_by_coin = metadata['sector']

    strategy_lookup = {item.name: item for item in build_strategy_definitions(config)}
    compare_names = [
        'TOP20_MOM_top8_biweekly__bull_only',
        'TOP20_SECTOR_top4_biweekly__bull_only',
    ]

    report_dir = ensure_dir(config.resolve_path(config.paths.reports_dir) / 'sector_lead_v3_scan')
    results = {}
    rows = []

    for name in compare_names:
        strategy = strategy_lookup[name]
        targets, _ = build_rebalance_targets(strategy, market, universe, regime_frame, config)
        result = run_backtest(
            name=name,
            asset_returns=market.returns,
            rebalance_targets=targets,
            sector_by_coin=sector_by_coin,
            friction=config.frictions,
            initial_capital=config.initial_capital,
        )
        results[name] = result
        metrics = compute_summary_metrics(result, config.annualization_days)
        metrics.update({'strategy': name, 'variant': 'BASELINE', 'frequency': 'biweekly', 'top_k': None, 'stop_lookback': None, 'immediate_reentry': False})
        rows.append(metrics)

    for top_k in [1, 2]:
        for frequency in ['biweekly', '7D']:
            build = build_sector_lead_v3_targets(
                market,
                universe,
                regime_frame,
                config,
                top_k=top_k,
                frequency=frequency,
                regime_mode='bull_only',
            )
            base_name = f'SECTOR_LEAD_V3_top{top_k}_{frequency}_NO_STOP'
            base_result = run_backtest(
                name=base_name,
                asset_returns=market.returns,
                rebalance_targets=build.targets,
                sector_by_coin=sector_by_coin,
                friction=config.frictions,
                initial_capital=config.initial_capital,
            )
            results[base_name] = base_result
            metrics = compute_summary_metrics(base_result, config.annualization_days)
            metrics.update({'strategy': base_name, 'variant': 'V3', 'frequency': frequency, 'top_k': top_k, 'stop_lookback': None, 'immediate_reentry': False})
            rows.append(metrics)
            build.sector_history.to_csv(report_dir / f'{base_name}_sector_history.csv', index=False)
            build.coin_history.to_csv(report_dir / f'{base_name}_coin_history.csv', index=False)

            for lookback in args.lookbacks:
                risk_on = btc_above_trailing_price(market.price, lookback_days=lookback, confirm_days=1)
                for immediate_reentry in [False, True]:
                    name = f'SECTOR_LEAD_V3_top{top_k}_{frequency}_BTC{lookback}_reentry_{int(immediate_reentry)}'
                    targets = apply_daily_risk_overlay(build.targets, risk_on, immediate_reentry=immediate_reentry)
                    result = run_backtest(
                        name=name,
                        asset_returns=market.returns,
                        rebalance_targets=targets,
                        sector_by_coin=sector_by_coin,
                        friction=config.frictions,
                        initial_capital=config.initial_capital,
                    )
                    results[name] = result
                    metrics = compute_summary_metrics(result, config.annualization_days)
                    metrics.update(
                        {
                            'strategy': name,
                            'variant': 'V3+STOP',
                            'frequency': frequency,
                            'top_k': top_k,
                            'stop_lookback': lookback,
                            'immediate_reentry': immediate_reentry,
                            'risk_on_fraction': float(risk_on.mean()),
                        }
                    )
                    rows.append(metrics)

    summary = pd.DataFrame(rows).set_index('strategy')
    momentum_base = summary.loc['TOP20_MOM_top8_biweekly__bull_only']
    summary['total_return_delta_vs_momentum'] = summary['total_return'] - momentum_base['total_return']
    summary['cagr_delta_vs_momentum'] = summary['cagr'] - momentum_base['cagr']
    summary['sharpe_delta_vs_momentum'] = summary['sharpe'] - momentum_base['sharpe']
    summary['drawdown_improvement_vs_momentum'] = summary['max_drawdown'] - momentum_base['max_drawdown']
    summary = summary.sort_values(['total_return', 'sharpe'], ascending=False)
    summary.to_csv(report_dir / 'sector_lead_v3_scan_summary.csv')

    top_plot_results = {name: results[name] for name in summary.head(8).index if name in results}
    plot_equity_curves(top_plot_results, report_dir / 'sector_lead_v3_scan_equity_curves.png')
    plot_drawdowns(top_plot_results, report_dir / 'sector_lead_v3_scan_drawdowns.png')
    pd.DataFrame({name: result.daily_returns for name, result in results.items()}).to_csv(report_dir / 'sector_lead_v3_scan_daily_returns.csv')
    pd.DataFrame({name: result.equity_curve for name, result in results.items()}).to_csv(report_dir / 'sector_lead_v3_scan_equity_curves.csv')

    markdown_lines = [
        '# Sector-Lead V3 Parameter Scan',
        '',
        f'Window: {config.start_date} to {config.end_date}',
        '',
        '## Top Results',
        '',
        dataframe_to_markdown(
            summary[['variant', 'frequency', 'top_k', 'stop_lookback', 'immediate_reentry', 'total_return', 'cagr', 'sharpe', 'max_drawdown', 'annualized_turnover', 'total_return_delta_vs_momentum', 'cagr_delta_vs_momentum']],
            percent_columns={'total_return', 'cagr', 'max_drawdown', 'total_return_delta_vs_momentum', 'cagr_delta_vs_momentum'},
            number_columns={'sharpe', 'annualized_turnover', 'top_k'},
        ),
        '',
        '## Notes',
        '',
        '- `frequency=7D` means weekly-style rebalancing every 7 days on the available daily index.',
        '- `immediate_reentry=True` means the strategy re-enters on the next trading day after BTC flips back to risk-on, using the latest desired target instead of waiting for the next scheduled rebalance.',
        '- Positive `total_return_delta_vs_momentum` means the variant beats `TOP20_MOM_top8_biweekly__bull_only` on full-period total return.',
    ]
    (report_dir / 'sector_lead_v3_scan_report.md').write_text('\n'.join(markdown_lines), encoding='utf-8')


if __name__ == '__main__':
    main()
