# Phase-Momentum Multiple-Testing Diagnostics

All candidate returns are net of 20 bps total trading cost. Every statistic uses the
same 1724 days (2022-01-01 to 2026-09-20); a candidate or benchmark
with a missing or non-finite day stops the run instead of being measured on fewer days.

## Identical candidates counted once

- none

## Candidate Sharpe dispersion

| index | candidate | annualized_sharpe | mean_daily_return | annualized_volatility |
| --- | --- | --- | --- | --- |
| 13 | LS47_H5_LS23_PROFITLOCK_REVERSAL_SHORT28_NOREENTRY | 2.0017 | 0.0028 | 0.5108 |
| 12 | LS46_H5_LS23_PROFITLOCK_REVERSAL_SHORT28 | 1.9913 | 0.0028 | 0.5108 |
| 11 | LS45_H5_LS23_PROFITLOCK_STRONGER21 | 1.9840 | 0.0028 | 0.5165 |
| 10 | LS43_H5_LS23_PROFITLOCK_STRONGER7 | 1.9661 | 0.0028 | 0.5175 |
| 9 | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE | 1.9583 | 0.0028 | 0.5183 |
| 8 | LS23_H5_PROFIT_LOCK_REGIME_SHORT | 1.9443 | 0.0027 | 0.5144 |
| 2 | LS17_H5_FUNDING_BASKET | 1.8543 | 0.0026 | 0.5027 |
| 1 | LS12_H5_REGIME_SHORT_ROUTER | 1.8515 | 0.0027 | 0.5332 |
| 7 | LS22_H5_EXTREME_RUN_PROFIT_LOCK | 1.8251 | 0.0025 | 0.5081 |
| 6 | LS21_H5_POSITIVE_CARRY_SHORT | 1.8097 | 0.0026 | 0.5315 |
| 3 | LS18_H5_FUNDING_TILT | 1.7695 | 0.0024 | 0.4885 |
| 5 | LS20_H5_COMMON_GROSS | 1.7677 | 0.0025 | 0.5110 |
| 0 | L125_BASELINE | 1.7325 | 0.0025 | 0.5280 |
| 4 | LS19_H5_REVERSAL_PAIR | 1.6964 | 0.0025 | 0.5309 |

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
| 0 | LS47_H5_LS23_PROFITLOCK_REVERSAL_SHORT28_NOREENTRY | family | 14.0000 | 0.1050 | 2.0017 | 0.1826 | 1.0000 |
| 1 | LS47_H5_LS23_PROFITLOCK_REVERSAL_SHORT28_NOREENTRY | top20_2022_trials | 6,142.0000 | 0.3173 | 2.0017 | 1.1866 | 0.9806 |
| 2 | LS47_H5_LS23_PROFITLOCK_REVERSAL_SHORT28_NOREENTRY | all_trials | 14,216.0000 | 0.3173 | 2.0017 | 1.2520 | 0.9713 |

## White Reality Check

One-sided stationary bootstrap for the best candidate mean. Against BTC the test
uses daily excess returns over BTC buy-and-hold. It covers only this family's
return series; earlier families kept no daily returns, so their selection is
priced by the project-scope Deflated Sharpe instead.

| index | benchmark | observed_max_mean_daily | reality_check_p_value | bootstrap_count |
| --- | --- | --- | --- | --- |
| 0 | zero | 0.0028 | 0.0040 | 1,000.0000 |
| 1 | BTC buy-and-hold | 0.0021 | 0.0090 | 1,000.0000 |

## CSCV / PBO

- PBO: 0.1775 (logit rule, lower is better)
- Median out-of-sample logit of the in-sample winner: 0.6931
- CSCV combinations: 924; rows used: 1724
- Most frequently selected candidate: `LS47_H5_LS23_PROFITLOCK_REVERSAL_SHORT28_NOREENTRY`

PBO judges the procedure "pick the best full-sample candidate". The fixed primary
was itself chosen with the full sample in view, so a PBO above 0.5 is evidence
against trusting the family's in-sample ranking, including the primary's place in it.
