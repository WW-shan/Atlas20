# Phase-Momentum Multiple-Testing Diagnostics

All candidate returns are net of 20 bps total trading cost. Every statistic uses the
same 1724 days (2022-01-01 to 2026-09-20); a candidate or benchmark
with a missing or non-finite day stops the run instead of being measured on fewer days.

## Identical candidates counted once

- none

## Candidate Sharpe dispersion

| index | candidate | annualized_sharpe | mean_daily_return | annualized_volatility |
| --- | --- | --- | --- | --- |
| 1 | LS3_H5_EXIT_SHORT21 | 1.8102 | 0.0026 | 0.5207 |
| 0 | H5_BASELINE | 1.7356 | 0.0020 | 0.4229 |

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
| 0 | LS3_H5_EXIT_SHORT21 | family | 2.0000 | 0.0528 | 1.8102 | 0.0274 | 1.0000 |
| 1 | LS3_H5_EXIT_SHORT21 | top20_2022_trials | 6,142.0000 | 0.3173 | 1.8102 | 1.1866 | 0.9277 |
| 2 | LS3_H5_EXIT_SHORT21 | all_trials | 14,173.0000 | 0.3173 | 1.8102 | 1.2517 | 0.9043 |

## White Reality Check

One-sided stationary bootstrap for the best candidate mean. Against BTC the test
uses daily excess returns over BTC buy-and-hold. It covers only this family's
return series; earlier families kept no daily returns, so their selection is
priced by the project-scope Deflated Sharpe instead.

| index | benchmark | observed_max_mean_daily | reality_check_p_value | bootstrap_count |
| --- | --- | --- | --- | --- |
| 0 | zero | 0.0026 | 0.0010 | 1,000.0000 |
| 1 | BTC buy-and-hold | 0.0019 | 0.0090 | 1,000.0000 |

## CSCV / PBO

- PBO: 0.8225 (logit rule, lower is better)
- Median out-of-sample logit of the in-sample winner: -0.6931
- CSCV combinations: 924; rows used: 1724
- Most frequently selected candidate: `LS3_H5_EXIT_SHORT21`

PBO judges the procedure "pick the best full-sample candidate". The fixed primary
was itself chosen with the full sample in view, so a PBO above 0.5 is evidence
against trusting the family's in-sample ranking, including the primary's place in it.
