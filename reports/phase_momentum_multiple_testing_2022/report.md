# Phase-Momentum Multiple-Testing Diagnostics

## Inputs

Best full-sample candidate by daily Sharpe: `rebalance_1d`.
Number of candidate trials: 32.
All candidate returns are net of 20 bps total trading cost.

## Candidate Sharpe dispersion

| index | candidate | annualized_sharpe | mean_daily_return | annualized_volatility |
| --- | --- | --- | --- | --- |
| 1 | rebalance_1d | 1.4663 | 0.0024 | 0.5950 |
| 16 | fixed_stop_20 | 1.4457 | 0.0023 | 0.5784 |
| 6 | target_vol_0.6 | 1.4375 | 0.0018 | 0.4506 |
| 18 | fixed_stop_30 | 1.4329 | 0.0022 | 0.5728 |
| 24 | trailing_stop_40 | 1.4325 | 0.0022 | 0.5728 |
| 19 | fixed_stop_40 | 1.4325 | 0.0022 | 0.5728 |
| 0 | primary | 1.4325 | 0.0022 | 0.5728 |
| 22 | trailing_stop_25 | 1.4299 | 0.0023 | 0.5785 |
| 7 | target_vol_0.7 | 1.4287 | 0.0020 | 0.5155 |
| 17 | fixed_stop_25 | 1.4272 | 0.0022 | 0.5721 |
| 23 | trailing_stop_30 | 1.4207 | 0.0022 | 0.5719 |
| 8 | target_vol_0.9 | 1.4127 | 0.0024 | 0.6181 |
| 21 | trailing_stop_20 | 1.4119 | 0.0022 | 0.5741 |
| 2 | rebalance_2d | 1.4115 | 0.0023 | 0.5850 |
| 9 | target_vol_1.0 | 1.4034 | 0.0025 | 0.6601 |
| 15 | fixed_stop_15 | 1.3756 | 0.0022 | 0.5786 |
| 31 | parameter_ensemble_20bps | 1.3293 | 0.0020 | 0.5497 |
| 3 | rebalance_5d | 1.3242 | 0.0020 | 0.5524 |
| 20 | trailing_stop_15 | 1.2987 | 0.0020 | 0.5636 |
| 25 | trend_50 | 1.2340 | 0.0022 | 0.6560 |
| 14 | no_vol_target | 1.2330 | 0.0027 | 0.7887 |
| 4 | hold_rank_1 | 1.2151 | 0.0020 | 0.6123 |
| 11 | btc_ma_150 | 1.1971 | 0.0018 | 0.5587 |
| 29 | trend_100_trailing_stop_20 | 1.1963 | 0.0021 | 0.6473 |
| 30 | trend_100_target_vol_0.7 | 1.1921 | 0.0019 | 0.5830 |
| 26 | trend_100 | 1.1851 | 0.0021 | 0.6474 |
| 5 | hold_rank_3 | 1.1176 | 0.0017 | 0.5581 |
| 10 | btc_ma_50 | 1.0881 | 0.0018 | 0.5913 |
| 27 | trend_150 | 1.0824 | 0.0019 | 0.6445 |
| 28 | trend_200 | 1.0754 | 0.0019 | 0.6490 |
| 12 | btc_ma_200 | 1.0128 | 0.0015 | 0.5474 |
| 13 | no_btc_gate | 0.6625 | 0.0013 | 0.7343 |

## Deflated Sharpe Ratio

- Observed annualized Sharpe: 1.4663
- Expected maximum Sharpe under the null: 0.3735
- Deflated Sharpe probability: 0.9959

## White Reality Check

- Observed maximum mean daily return: 0.002664
- Stationary-bootstrap p-value: 0.0230
- Bootstrap count: 1000

## CSCV / PBO

- PBO: 0.6288
- Median out-of-sample percentile of the in-sample winner: 0.4375
- Mean out-of-sample percentile of the in-sample winner: 0.4217
- CSCV combinations: 924
- Most frequently selected candidate: `rebalance_1d`

## Interpretation

- DSR probability is the probability that the observed Sharpe exceeds the
  expected maximum Sharpe under the null after accounting for trial count.
- The Reality Check p-value is one-sided for positive mean return; it does
  not test whether the strategy beats BTC.
- PBO is the fraction of CSCV splits where the in-sample winner lands in
  the bottom half out of sample. Lower is better.
