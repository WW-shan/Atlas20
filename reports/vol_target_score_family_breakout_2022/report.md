# Phase-Invariant Volatility-Target Validation

This study keeps CTREND-lite breakout top-1 selection and replaces the
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
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.1242 | 0.3498 | 1.0097 | -0.3895 | 2.4690 | 0.9843 | 1.6704 | 1.0662 | -0.2170 | 1.3299 | 0.7534 | 0.9045 | -1.8054 | -0.3895 | 3.5381 | 1.2145 | 11.9778 | 0.7700 | -0.7199 | 0.3208 | 17.3432 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.6718 | 0.3170 | 1.0275 | -0.3431 | 2.3324 | 1.0162 | 1.5742 | 1.0566 | -0.1976 | 1.3119 | 0.7816 | 0.9505 | -1.8060 | -0.3431 | 3.2752 | 1.2720 | 9.6271 | 0.7631 | -0.6585 | 0.2852 | 15.4827 |

## Top candidates by 2025-2026 test multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.1242 | 0.3498 | 1.0097 | -0.3895 | 2.4690 | 0.9843 | 1.6704 | 1.0662 | -0.2170 | 1.3299 | 0.7534 | 0.9045 | -1.8054 | -0.3895 | 3.5381 | 1.2145 | 11.9778 | 0.7700 | -0.7199 | 0.3208 | 17.3432 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.6718 | 0.3170 | 1.0275 | -0.3431 | 2.3324 | 1.0162 | 1.5742 | 1.0566 | -0.1976 | 1.3119 | 0.7816 | 0.9505 | -1.8060 | -0.3431 | 3.2752 | 1.2720 | 9.6271 | 0.7631 | -0.6585 | 0.2852 | 15.4827 |

## Interpretation guardrail

A candidate is not promoted because of one phase or one full-sample
maximum. The basket, train/test split, exposure level, and neighboring
volatility windows must all be economically consistent.
