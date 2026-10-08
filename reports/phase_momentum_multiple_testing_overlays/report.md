# Phase-Momentum Multiple-Testing Diagnostics

All candidate returns are net of 20 bps total trading cost. Every statistic uses the
same 1725 days (2022-01-01 to 2026-09-21); a candidate or benchmark
with a missing or non-finite day stops the run instead of being measured on fewer days.

## Identical candidates counted once

- `fixed_stop_40` is identical to `primary`
- `trailing_stop_40` is identical to `primary`

## Candidate Sharpe dispersion

| index | candidate | annualized_sharpe | mean_daily_return | annualized_volatility |
| --- | --- | --- | --- | --- |
| 34 | h5_disp_p75 | 1.6836 | 0.0020 | 0.4411 |
| 35 | h5_disp_p90 | 1.6181 | 0.0022 | 0.4882 |
| 33 | h5_disp_p60 | 1.5995 | 0.0018 | 0.4060 |
| 31 | h3_breadth_050 | 1.5233 | 0.0022 | 0.5163 |
| 30 | h3_breadth_045 | 1.5123 | 0.0022 | 0.5228 |
| 1 | rebalance_1d | 1.4663 | 0.0024 | 0.5950 |
| 23 | trend_50 | 1.4530 | 0.0023 | 0.5727 |
| 32 | h3_breadth_055 | 1.4496 | 0.0020 | 0.5078 |
| 16 | fixed_stop_20 | 1.4457 | 0.0023 | 0.5784 |
| 6 | target_vol_0.6 | 1.4375 | 0.0018 | 0.4506 |
| 18 | fixed_stop_30 | 1.4329 | 0.0022 | 0.5728 |
| 0 | primary | 1.4325 | 0.0022 | 0.5728 |
| 21 | trailing_stop_25 | 1.4299 | 0.0023 | 0.5785 |
| 7 | target_vol_0.7 | 1.4287 | 0.0020 | 0.5155 |
| 17 | fixed_stop_25 | 1.4272 | 0.0022 | 0.5721 |
| 22 | trailing_stop_30 | 1.4207 | 0.0022 | 0.5719 |
| 8 | target_vol_0.9 | 1.4127 | 0.0024 | 0.6181 |
| 20 | trailing_stop_20 | 1.4119 | 0.0022 | 0.5741 |
| 2 | rebalance_2d | 1.4115 | 0.0023 | 0.5850 |
| 9 | target_vol_1.0 | 1.4034 | 0.0025 | 0.6601 |
| 15 | fixed_stop_15 | 1.3756 | 0.0022 | 0.5786 |
| 29 | parameter_ensemble_20bps | 1.3403 | 0.0020 | 0.5525 |
| 25 | trend_150 | 1.3356 | 0.0021 | 0.5623 |
| 27 | trend_100_trailing_stop_20 | 1.3334 | 0.0021 | 0.5641 |
| 24 | trend_100 | 1.3282 | 0.0020 | 0.5624 |
| 3 | rebalance_5d | 1.3242 | 0.0020 | 0.5524 |
| 28 | trend_100_target_vol_0.7 | 1.3231 | 0.0018 | 0.5070 |
| 19 | trailing_stop_15 | 1.2987 | 0.0020 | 0.5636 |
| 14 | no_vol_target | 1.2330 | 0.0027 | 0.7887 |
| 4 | hold_rank_1 | 1.2151 | 0.0020 | 0.6123 |
| 11 | btc_ma_150 | 1.1971 | 0.0018 | 0.5587 |
| 26 | trend_200 | 1.1811 | 0.0018 | 0.5571 |
| 5 | hold_rank_3 | 1.1176 | 0.0017 | 0.5581 |
| 10 | btc_ma_50 | 1.0881 | 0.0018 | 0.5913 |
| 12 | btc_ma_200 | 1.0128 | 0.0015 | 0.5474 |
| 13 | no_btc_gate | 0.6625 | 0.0013 | 0.7343 |

## Deflated Sharpe Ratio

`family` uses only the unique phase-momentum candidates and their own Sharpe
dispersion. The project scopes come from `reports/research_trial_inventory/summary.json`:
`top20_2022_trials` counts every configuration the project backtested on Top20 from
2022-01-01, the comparable pool the champion was selected from; `all_trials` counts every
configuration on any window or universe. Both use the Sharpe dispersion of the
Top20/2022 pool, because Sharpe ratios on other windows are not comparable. A
probability above 0.95 passes.

| index | candidate | scope | trial_count | trial_sharpe_std_annualized | observed_sharpe | expected_max_sharpe | deflated_sharpe_probability |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | h5_disp_p75 | family | 36.0000 | 0.1853 | 1.6836 | 0.3980 | 0.9992 |
| 1 | h5_disp_p75 | top20_2022_trials | 6,135.0000 | 0.3155 | 1.6836 | 1.1797 | 0.8917 |
| 2 | h5_disp_p75 | all_trials | 14,129.0000 | 0.3155 | 1.6836 | 1.2443 | 0.8593 |

## White Reality Check

One-sided stationary bootstrap for the best candidate mean. Against BTC the test
uses daily excess returns over BTC buy-and-hold. It covers only this family's
return series; earlier families kept no daily returns, so their selection is
priced by the project-scope Deflated Sharpe instead.

| index | benchmark | observed_max_mean_daily | reality_check_p_value | bootstrap_count |
| --- | --- | --- | --- | --- |
| 0 | zero | 0.0027 | 0.0190 | 1,000.0000 |
| 1 | BTC buy-and-hold | 0.0019 | 0.0250 | 1,000.0000 |

## CSCV / PBO

- PBO: 0.1916 (logit rule, lower is better)
- Median out-of-sample logit of the in-sample winner: 2.8622
- CSCV combinations: 924; rows used: 1725
- Most frequently selected candidate: `h5_disp_p75`

PBO judges the procedure "pick the best full-sample candidate". The fixed primary
was itself chosen with the full sample in view, so a PBO above 0.5 is evidence
against trusting the family's in-sample ranking, including the primary's place in it.
