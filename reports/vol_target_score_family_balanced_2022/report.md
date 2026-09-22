# Phase-Invariant Volatility-Target Validation

This study keeps CTREND-lite balanced top-1 selection and replaces the
binary BTC gate with a capped volatility-target exposure. Every cycle is
evaluated as an equal-weight basket of all calendar phases, so the result
does not depend on a fixed start date. No leverage is allowed. The fast
simulator lets weights drift between target events, matching the
production engine instead of assuming free daily rebalancing.

## External evidence

- Moreira and Muir, *Volatility-Managed Portfolios*: scaling exposure by
  realized volatility can improve risk-adjusted outcomes.
  <https://doi.org/10.1111/jofi.12467>
- Yang, *Cryptocurrency market risk-managed momentum strategies*:
  volatility scaling improved crypto momentum Sharpe and returns.
  <https://doi.org/10.1016/j.frl.2025.107879>
- Man Group, *In Crypto We Trend*: volatility scaling can reduce
  pressure-period turnover while preserving trend exposure.
  <https://www.man.com/insights/in-crypto-we-trend>

## Top candidates by full-period basket multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.7529 | 0.3910 | 1.0702 | -0.3810 | 2.7151 | 1.0491 | 1.7505 | 1.1167 | -0.1824 | 1.3819 | 0.7826 | 0.9732 | -1.5571 | -0.3810 | 4.0519 | 1.1844 | 11.6292 | 0.8471 | -0.6261 | 0.3120 | 16.8352 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.1379 | 0.3508 | 1.0915 | -0.3350 | 2.5144 | 1.0791 | 1.6456 | 1.1214 | -0.1605 | 1.3462 | 0.8117 | 1.0054 | -1.5665 | -0.3350 | 3.6295 | 1.2839 | 9.1276 | 0.8404 | -0.5667 | 0.2748 | 14.7618 |

## Top candidates by 2025-2026 test multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.7529 | 0.3910 | 1.0702 | -0.3810 | 2.7151 | 1.0491 | 1.7505 | 1.1167 | -0.1824 | 1.3819 | 0.7826 | 0.9732 | -1.5571 | -0.3810 | 4.0519 | 1.1844 | 11.6292 | 0.8471 | -0.6261 | 0.3120 | 16.8352 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.1379 | 0.3508 | 1.0915 | -0.3350 | 2.5144 | 1.0791 | 1.6456 | 1.1214 | -0.1605 | 1.3462 | 0.8117 | 1.0054 | -1.5665 | -0.3350 | 3.6295 | 1.2839 | 9.1276 | 0.8404 | -0.5667 | 0.2748 | 14.7618 |

## Interpretation guardrail

A candidate is not promoted because of one phase or one full-sample
maximum. The basket, train/test split, exposure level, and neighboring
volatility windows must all be economically consistent.
