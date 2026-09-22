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
| 21 | 7.0000 | 0.8000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.6864 | 0.4448 | 0.9563 | -0.5064 | 3.1708 | 0.9653 | 1.7933 | 0.9443 | -0.2927 | 1.3317 | 0.6275 | 0.8382 | -1.6503 | -0.5064 | 4.4313 | 0.6758 | 21.8024 | 0.8067 | -0.7632 | 0.3898 | 35.1186 |
| 15 | 7.0000 | 0.7000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.5813 | 0.4391 | 0.9867 | -0.4781 | 3.0790 | 0.9846 | 1.8127 | 0.9964 | -0.2622 | 1.3453 | 0.6472 | 0.8827 | -1.6909 | -0.4781 | 4.3364 | 0.7822 | 18.6557 | 0.8236 | -0.7110 | 0.3643 | 32.9261 |
| 45 | 14.0000 | 0.8000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.2168 | 0.4187 | 1.0055 | -0.4541 | 2.8265 | 0.9738 | 1.8457 | 1.0739 | -0.2329 | 1.3733 | 0.7407 | 0.8738 | -1.4807 | -0.4541 | 4.4578 | 0.9069 | 16.5074 | 0.8133 | -0.7172 | 0.3623 | 19.4112 |
| 39 | 14.0000 | 0.7000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.2138 | 0.4185 | 1.0488 | -0.4209 | 2.8612 | 1.0226 | 1.8223 | 1.1068 | -0.2081 | 1.3970 | 0.7613 | 0.9416 | -1.5169 | -0.4209 | 4.5406 | 1.0529 | 14.5934 | 0.8473 | -0.6720 | 0.3411 | 18.3148 |
| 9 | 7.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.9810 | 0.4049 | 0.9956 | -0.4390 | 2.8170 | 0.9841 | 1.7682 | 1.0224 | -0.2305 | 1.3357 | 0.6667 | 0.9152 | -1.7298 | -0.4390 | 3.9168 | 0.8542 | 15.1895 | 0.8224 | -0.6498 | 0.3335 | 30.1153 |
| 33 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.7529 | 0.3910 | 1.0702 | -0.3810 | 2.7151 | 1.0491 | 1.7505 | 1.1167 | -0.1824 | 1.3819 | 0.7826 | 0.9732 | -1.5571 | -0.3810 | 4.0519 | 1.1844 | 11.6292 | 0.8471 | -0.6261 | 0.3120 | 16.8352 |
| 3 | 7.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.2407 | 0.3578 | 1.0032 | -0.3954 | 2.4940 | 0.9759 | 1.7003 | 1.0601 | -0.1961 | 1.3296 | 0.7005 | 0.9302 | -1.7409 | -0.3954 | 3.5299 | 0.9279 | 11.8597 | 0.8359 | -0.5854 | 0.2921 | 26.4010 |
| 27 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.1379 | 0.3508 | 1.0915 | -0.3350 | 2.5144 | 1.0791 | 1.6456 | 1.1214 | -0.1605 | 1.3462 | 0.8117 | 1.0054 | -1.5665 | -0.3350 | 3.6295 | 1.2839 | 9.1276 | 0.8404 | -0.5667 | 0.2748 | 14.7618 |

## Top candidates by 2025-2026 test multiple at 20bps

| index | cycle_days | target_volatility | vol_window | stop_mode | gate_mode | cost_bps | basket_multiple | basket_cagr | basket_sharpe | basket_max_drawdown | train_multiple | train_sharpe | test_multiple | test_sharpe | test_max_drawdown | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling_1y_median_sharpe | rolling_1y_worst_sharpe | rolling_1y_worst_drawdown | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_exposure | phase_median_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 45 | 14.0000 | 0.8000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.2168 | 0.4187 | 1.0055 | -0.4541 | 2.8265 | 0.9738 | 1.8457 | 1.0739 | -0.2329 | 1.3733 | 0.7407 | 0.8738 | -1.4807 | -0.4541 | 4.4578 | 0.9069 | 16.5074 | 0.8133 | -0.7172 | 0.3623 | 19.4112 |
| 39 | 14.0000 | 0.7000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.2138 | 0.4185 | 1.0488 | -0.4209 | 2.8612 | 1.0226 | 1.8223 | 1.1068 | -0.2081 | 1.3970 | 0.7613 | 0.9416 | -1.5169 | -0.4209 | 4.5406 | 1.0529 | 14.5934 | 0.8473 | -0.6720 | 0.3411 | 18.3148 |
| 15 | 7.0000 | 0.7000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.5813 | 0.4391 | 0.9867 | -0.4781 | 3.0790 | 0.9846 | 1.8127 | 0.9964 | -0.2622 | 1.3453 | 0.6472 | 0.8827 | -1.6909 | -0.4781 | 4.3364 | 0.7822 | 18.6557 | 0.8236 | -0.7110 | 0.3643 | 32.9261 |
| 21 | 7.0000 | 0.8000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 5.6864 | 0.4448 | 0.9563 | -0.5064 | 3.1708 | 0.9653 | 1.7933 | 0.9443 | -0.2927 | 1.3317 | 0.6275 | 0.8382 | -1.6503 | -0.5064 | 4.4313 | 0.6758 | 21.8024 | 0.8067 | -0.7632 | 0.3898 | 35.1186 |
| 9 | 7.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.9810 | 0.4049 | 0.9956 | -0.4390 | 2.8170 | 0.9841 | 1.7682 | 1.0224 | -0.2305 | 1.3357 | 0.6667 | 0.9152 | -1.7298 | -0.4390 | 3.9168 | 0.8542 | 15.1895 | 0.8224 | -0.6498 | 0.3335 | 30.1153 |
| 33 | 14.0000 | 0.6000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.7529 | 0.3910 | 1.0702 | -0.3810 | 2.7151 | 1.0491 | 1.7505 | 1.1167 | -0.1824 | 1.3819 | 0.7826 | 0.9732 | -1.5571 | -0.3810 | 4.0519 | 1.1844 | 11.6292 | 0.8471 | -0.6261 | 0.3120 | 16.8352 |
| 3 | 7.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.2407 | 0.3578 | 1.0032 | -0.3954 | 2.4940 | 0.9759 | 1.7003 | 1.0601 | -0.1961 | 1.3296 | 0.7005 | 0.9302 | -1.7409 | -0.3954 | 3.5299 | 0.9279 | 11.8597 | 0.8359 | -0.5854 | 0.2921 | 26.4010 |
| 27 | 14.0000 | 0.5000 | 60.0000 | own75 | btc_ma100 | 20.0000 | 4.1379 | 0.3508 | 1.0915 | -0.3350 | 2.5144 | 1.0791 | 1.6456 | 1.1214 | -0.1605 | 1.3462 | 0.8117 | 1.0054 | -1.5665 | -0.3350 | 3.6295 | 1.2839 | 9.1276 | 0.8404 | -0.5667 | 0.2748 | 14.7618 |

## Interpretation guardrail

A candidate is not promoted because of one phase or one full-sample
maximum. The basket, train/test split, exposure level, and neighboring
volatility windows must all be economically consistent.
