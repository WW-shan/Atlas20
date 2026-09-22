# Phase-Invariant Volatility-Target Validation

This study keeps CTREND-lite acceleration top-1 selection and replaces the
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
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.4416 | 0.2991 | 0.9207 | -0.4020 | 2.6581 | 1.0617 | 1.2948 | 0.6379 | -0.3138 | 1.2881 | 0.7337 | 0.8654 | -1.4056 | -0.4020 | 2.6981 | 1.0960 | 10.5942 | 0.6761 | -0.7154 | 0.3234 | 18.5094 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.2032 | 0.2795 | 0.9494 | -0.3533 | 2.5372 | 1.1027 | 1.2625 | 0.6363 | -0.2688 | 1.2976 | 0.7728 | 0.9255 | -1.4205 | -0.3533 | 2.6076 | 1.2257 | 7.5259 | 0.7055 | -0.6587 | 0.2944 | 16.6299 |

## Top candidates by 2025-2026 test multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.4416 | 0.2991 | 0.9207 | -0.4020 | 2.6581 | 1.0617 | 1.2948 | 0.6379 | -0.3138 | 1.2881 | 0.7337 | 0.8654 | -1.4056 | -0.4020 | 2.6981 | 1.0960 | 10.5942 | 0.6761 | -0.7154 | 0.3234 | 18.5094 |
| 1 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 3.2032 | 0.2795 | 0.9494 | -0.3533 | 2.5372 | 1.1027 | 1.2625 | 0.6363 | -0.2688 | 1.2976 | 0.7728 | 0.9255 | -1.4205 | -0.3533 | 2.6076 | 1.2257 | 7.5259 | 0.7055 | -0.6587 | 0.2944 | 16.6299 |

## Interpretation guardrail

A candidate is not promoted because of one phase or one full-sample
maximum. The basket, train/test split, exposure level, and neighboring
volatility windows must all be economically consistent.
