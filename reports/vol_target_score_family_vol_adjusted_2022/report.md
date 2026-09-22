# Phase-Invariant Volatility-Target Validation

This study keeps CTREND-lite vol_adjusted top-1 selection and replaces the
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
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 1.9249 | 0.1487 | 0.6324 | -0.3124 | 1.4153 | 0.5155 | 1.3601 | 1.0081 | -0.1401 | 1.1769 | 0.8683 | 0.6931 | -1.1496 | -0.3124 | 1.4905 | 0.9321 | 4.0218 | 0.4021 | -0.5014 | 0.3373 | 15.8039 |
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 1.8648 | 0.1410 | 0.5973 | -0.3326 | 1.3587 | 0.4680 | 1.3725 | 0.9856 | -0.1491 | 1.1573 | 0.8592 | 0.6290 | -1.1020 | -0.3326 | 1.4643 | 0.8901 | 3.6766 | 0.3760 | -0.5453 | 0.3528 | 16.5366 |

## Top candidates by 2025-2026 test multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 1.8648 | 0.1410 | 0.5973 | -0.3326 | 1.3587 | 0.4680 | 1.3725 | 0.9856 | -0.1491 | 1.1573 | 0.8592 | 0.6290 | -1.1020 | -0.3326 | 1.4643 | 0.8901 | 3.6766 | 0.3760 | -0.5453 | 0.3528 | 16.5366 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 1.9249 | 0.1487 | 0.6324 | -0.3124 | 1.4153 | 0.5155 | 1.3601 | 1.0081 | -0.1401 | 1.1769 | 0.8683 | 0.6931 | -1.1496 | -0.3124 | 1.4905 | 0.9321 | 4.0218 | 0.4021 | -0.5014 | 0.3373 | 15.8039 |

## Interpretation guardrail

A candidate is not promoted because of one phase or one full-sample
maximum. The basket, train/test split, exposure level, and neighboring
volatility windows must all be economically consistent.
