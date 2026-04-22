from __future__ import annotations

import argparse
import itertools
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
from atlas20.reporting.report import dataframe_to_markdown
from atlas20.signals.regime import build_regime_frame
from atlas20.signals.risk import btc_above_trailing_price
from atlas20.strategies.momentum_lead import build_momentum_lead_targets
from atlas20.strategies.overlays import apply_daily_risk_overlay
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data


WEIGHT_VARIANTS: dict[str, dict[str, float]] = {
    'base': {
        'momentum_rank': 0.45,
        'ret_21_rank': 0.25,
        'ret_42_rank': 0.20,
        'near_high_rank': 0.10,
    },
    'short_accel': {
        'momentum_rank': 0.35,
        'ret_21_rank': 0.35,
        'ret_42_rank': 0.15,
        'near_high_rank': 0.15,
    },
    'breakout': {
        'momentum_rank': 0.30,
        'ret_21_rank': 0.20,
        'ret_42_rank': 0.15,
        'near_high_rank': 0.35,
    },
    'balanced': {
        'momentum_rank': 0.40,
        'ret_21_rank': 0.20,
        'ret_42_rank': 0.20,
        'near_high_rank': 0.20,
    },
}

PARKING_TARGETS = {
    'cash': None,
    'btc': pd.Series({'bitcoin': 1.0}),
    'eth': pd.Series({'ethereum': 1.0}),
}



def _all_rebalance_dates(index: pd.DatetimeIndex, config) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    for frequency_name, frequency_value in config.rebalancing.frequencies.items():
        dates.update(get_rebalance_dates(index, config.start_timestamp, frequency_name, frequency_value))
    return sorted(dates)



def main() -> None:
    parser = argparse.ArgumentParser(description='Refine the best non-levered profit-maximization candidates.')
    parser.add_argument('--config', default='config/bear_bottom_to_current_2022_11_21_2026_04_22.yaml')
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    sector_config = load_sector_config(config.resolve_path('config/sectors.yaml'))
    panel, metadata = build_processed_datasets(config, sector_config)
    market = prepare_market_data(panel, metadata, config)
    sector_by_coin = metadata['sector']
    report_dir = ensure_dir(config.resolve_path(config.paths.reports_dir) / 'profit_max_refine')

    rows = []
    for universe_label, min_hist, min_vol in [('strict', 90, 25_000_000), ('medium', 60, 10_000_000), ('loose', 30, 5_000_000)]:
        local_config = config.model_copy(deep=True)
        local_config.universe.min_history_days = min_hist
        local_config.universe.min_daily_dollar_volume = min_vol
        union_rebalance_dates = _all_rebalance_dates(market.price.index, local_config)
        universe = build_rebalance_universe(market, union_rebalance_dates, local_config)
        regime_frame = build_regime_frame(market.price, market.market_cap, local_config)
        earliest = pd.to_datetime(universe['rebalance_date']).min()

        for top_n, frequency, weight_name in itertools.product([1, 2], ['7D', 'biweekly'], WEIGHT_VARIANTS.keys()):
            base_targets = build_momentum_lead_targets(
                market,
                universe,
                regime_frame,
                local_config,
                top_n=top_n,
                frequency=frequency,
                regime_mode='bull_only',
                weighted=(top_n > 1),
                score_weights=WEIGHT_VARIANTS[weight_name],
            ).targets

            for stop_lb, immediate_reentry, seed_name, park_name in itertools.product([12, 13, 14, 15], [False, True], PARKING_TARGETS.keys(), PARKING_TARGETS.keys()):
                risk_on = btc_above_trailing_price(market.price, lookback_days=stop_lb, confirm_days=1)
                targets = apply_daily_risk_overlay(
                    base_targets,
                    risk_on,
                    immediate_reentry=immediate_reentry,
                    risk_off_target=PARKING_TARGETS[park_name],
                    initial_target=PARKING_TARGETS[seed_name],
                )
                result = run_backtest(
                    name='scan',
                    asset_returns=market.returns,
                    rebalance_targets=targets,
                    sector_by_coin=sector_by_coin,
                    friction=local_config.frictions,
                    initial_capital=local_config.initial_capital,
                    gross_target_exposure=1.0,
                )
                metrics = compute_summary_metrics(result, local_config.annualization_days)
                rows.append(
                    {
                        'universe_setting': universe_label,
                        'min_history_days': min_hist,
                        'min_daily_dollar_volume': min_vol,
                        'earliest_universe_date': earliest,
                        'top_n': top_n,
                        'frequency': frequency,
                        'weight_name': weight_name,
                        'stop_lookback': stop_lb,
                        'immediate_reentry': immediate_reentry,
                        'seed_asset': seed_name,
                        'risk_off_asset': park_name,
                        **metrics,
                    }
                )

    summary = pd.DataFrame(rows)
    summary['multiple'] = summary['total_return'] + 1.0
    summary = summary.sort_values(['multiple', 'sharpe'], ascending=[False, False])
    summary.to_csv(report_dir / 'profit_max_refine_summary.csv', index=False)
    summary.head(50).to_csv(report_dir / 'profit_max_refine_top50.csv', index=False)

    markdown_lines = [
        '# Profit Max Refine Search',
        '',
        f'Window: {config.start_date} to {config.end_date}',
        '',
        '## Top Results',
        '',
        dataframe_to_markdown(
            summary.head(25)[[
                'universe_setting', 'top_n', 'frequency', 'weight_name', 'stop_lookback',
                'immediate_reentry', 'seed_asset', 'risk_off_asset', 'multiple', 'cagr',
                'sharpe', 'max_drawdown', 'annualized_turnover'
            ]],
            percent_columns={'cagr', 'max_drawdown'},
            number_columns={'top_n', 'stop_lookback', 'multiple', 'sharpe', 'annualized_turnover'},
        ),
    ]
    (report_dir / 'profit_max_refine_report.md').write_text('\n'.join(markdown_lines), encoding='utf-8')


if __name__ == '__main__':
    main()
