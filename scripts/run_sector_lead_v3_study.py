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
from atlas20.reporting.charts import plot_drawdowns, plot_equity_curves, plot_sector_exposure
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
    parser = argparse.ArgumentParser(description='Run Sector-Lead V3 study for Atlas20.')
    parser.add_argument('--config', default='config/five_year_exact_2021_04_22_2026_04_22.yaml')
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
    risk_21d = btc_above_trailing_price(market.price, lookback_days=21, confirm_days=1)

    strategy_lookup = {item.name: item for item in build_strategy_definitions(config)}
    compare_names = [
        'TOP20_MOM_top8_biweekly__bull_only',
        'TOP20_SECTOR_top4_biweekly__bull_only',
    ]

    results = {}
    rows = []
    report_dir = ensure_dir(config.resolve_path(config.paths.reports_dir) / 'sector_lead_v3_study')

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
        metrics.update({'strategy': name, 'variant': 'BASELINE'})
        rows.append(metrics)

    variants = [
        ('SECTOR_LEAD_V3A_top2_biweekly__bull_only', dict(top_k=2, frequency='biweekly', regime_mode='bull_only'), False),
        ('SECTOR_LEAD_V3B_top1_biweekly__bull_only', dict(top_k=1, frequency='biweekly', regime_mode='bull_only'), False),
        ('SECTOR_LEAD_V3C_top2_biweekly__bull_only__BTC_LT_21D', dict(top_k=2, frequency='biweekly', regime_mode='bull_only'), True),
        ('SECTOR_LEAD_V3D_top1_biweekly__bull_only__BTC_LT_21D', dict(top_k=1, frequency='biweekly', regime_mode='bull_only'), True),
    ]

    for variant_name, kwargs, use_stop in variants:
        build = build_sector_lead_v3_targets(market, universe, regime_frame, config, **kwargs)
        targets = apply_daily_risk_overlay(build.targets, risk_21d) if use_stop else build.targets
        result = run_backtest(
            name=variant_name,
            asset_returns=market.returns,
            rebalance_targets=targets,
            sector_by_coin=sector_by_coin,
            friction=config.frictions,
            initial_capital=config.initial_capital,
        )
        results[variant_name] = result
        metrics = compute_summary_metrics(result, config.annualization_days)
        metrics.update({'strategy': variant_name, 'variant': variant_name.split('_')[2] if 'BTC' not in variant_name else 'V3+STOP'})
        rows.append(metrics)
        build.sector_history.to_csv(report_dir / f'{variant_name}_sector_history.csv', index=False)
        build.coin_history.to_csv(report_dir / f'{variant_name}_coin_history.csv', index=False)
        plot_sector_exposure(result.sector_exposure, report_dir / f'{variant_name}_sector_exposure.png', title=f'Sector Exposure - {variant_name}')

    summary = pd.DataFrame(rows).set_index('strategy')
    baseline = summary.loc['TOP20_MOM_top8_biweekly__bull_only']
    summary['cagr_delta_vs_best_momentum'] = summary['cagr'] - baseline['cagr']
    summary['sharpe_delta_vs_best_momentum'] = summary['sharpe'] - baseline['sharpe']
    summary['drawdown_improvement_vs_best_momentum'] = summary['max_drawdown'] - baseline['max_drawdown']
    summary = summary.sort_values(['cagr', 'sharpe'], ascending=False)
    summary.to_csv(report_dir / 'sector_lead_v3_summary.csv')
    pd.DataFrame({name: result.daily_returns for name, result in results.items()}).to_csv(report_dir / 'sector_lead_v3_daily_returns.csv')
    pd.DataFrame({name: result.equity_curve for name, result in results.items()}).to_csv(report_dir / 'sector_lead_v3_equity_curves.csv')
    pd.DataFrame({name: result.drawdown for name, result in results.items()}).to_csv(report_dir / 'sector_lead_v3_drawdowns.csv')
    plot_equity_curves(results, report_dir / 'sector_lead_v3_equity_curves.png')
    plot_drawdowns(results, report_dir / 'sector_lead_v3_drawdowns.png')

    markdown_lines = [
        '# Sector-Lead V3 Study',
        '',
        f'Window: {config.start_date} to {config.end_date}',
        '',
        '## Summary',
        '',
        dataframe_to_markdown(
            summary[['variant', 'cagr', 'sharpe', 'max_drawdown', 'annualized_turnover', 'average_holdings', 'cagr_delta_vs_best_momentum', 'sharpe_delta_vs_best_momentum', 'drawdown_improvement_vs_best_momentum']],
            percent_columns={'cagr', 'max_drawdown', 'cagr_delta_vs_best_momentum', 'drawdown_improvement_vs_best_momentum'},
            number_columns={'sharpe', 'annualized_turnover', 'average_holdings', 'sharpe_delta_vs_best_momentum'},
        ),
        '',
        '## Variant definitions',
        '',
        '- `BASELINE`: best existing momentum and sector references from the main pipeline.',
        '- `V3A`: top 2 sectors, concentrated 60/40 weights, one leader per sector, no daily stop overlay.',
        '- `V3B`: top 1 sector, 100% in the sector leader, no daily stop overlay.',
        '- `V3+STOP`: same concentrated sector-lead constructions but with BTC 21-day trailing-price risk-off overlay.',
        '',
        '## Notes',
        '',
        '- Sector-Lead V3 reduces sector diversification on purpose to chase theme leaders.',
        '- Positive `drawdown_improvement_vs_best_momentum` means a shallower drawdown than `TOP20_MOM_top8_biweekly__bull_only`.',
    ]
    (report_dir / 'sector_lead_v3_report.md').write_text('\n'.join(markdown_lines), encoding='utf-8')


if __name__ == '__main__':
    main()
