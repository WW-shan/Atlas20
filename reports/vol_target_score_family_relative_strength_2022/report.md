# Phase-Invariant Volatility-Target Validation

This study keeps CTREND-lite relative_strength top-1 selection and replaces the
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
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.5437 | 0.3778 | 1.0702 | -0.3488 | 2.7467 | 1.0854 | 1.6542 | 1.0454 | -0.1812 | 1.3973 | 0.7989 | 1.0317 | -1.4021 | -0.3488 | 2.9540 | 1.5494 | 17.8969 | 0.6885 | -0.6739 | 0.2906 | 15.6516 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.9174 | 0.3352 | 1.0914 | -0.3012 | 2.5153 | 1.1174 | 1.5575 | 1.0454 | -0.1526 | 1.3572 | 0.8266 | 1.0636 | -1.4117 | -0.3012 | 2.7019 | 1.6221 | 13.2227 | 0.6807 | -0.6090 | 0.2528 | 13.6695 |

## Top candidates by 2025-2026 test multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.5437 | 0.3778 | 1.0702 | -0.3488 | 2.7467 | 1.0854 | 1.6542 | 1.0454 | -0.1812 | 1.3973 | 0.7989 | 1.0317 | -1.4021 | -0.3488 | 2.9540 | 1.5494 | 17.8969 | 0.6885 | -0.6739 | 0.2906 | 15.6516 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.9174 | 0.3352 | 1.0914 | -0.3012 | 2.5153 | 1.1174 | 1.5575 | 1.0454 | -0.1526 | 1.3572 | 0.8266 | 1.0636 | -1.4117 | -0.3012 | 2.7019 | 1.6221 | 13.2227 | 0.6807 | -0.6090 | 0.2528 | 13.6695 |

## Interpretation guardrail

A candidate is not promoted because of one phase or one full-sample
maximum. The basket, train/test split, exposure level, and neighboring
volatility windows must all be economically consistent.
