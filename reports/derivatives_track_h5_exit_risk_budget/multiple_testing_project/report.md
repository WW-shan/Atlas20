# Phase-Momentum Multiple-Testing Diagnostics

All candidate returns are net of 20 bps total trading cost. Every statistic uses the
same 1724 days (2022-01-01 to 2026-09-20); a candidate or benchmark
with a missing or non-finite day stops the run instead of being measured on fewer days.

## Identical candidates counted once

- none

## Candidate Sharpe dispersion

| index | candidate | annualized_sharpe | mean_daily_return | annualized_volatility |
| --- | --- | --- | --- | --- |
| 1 | LS4_H5_EXIT_RISK05 | 1.8085 | 0.0021 | 0.4176 |
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
| 0 | LS4_H5_EXIT_RISK05 | family | 2.0000 | 0.0516 | 1.8085 | 0.0268 | 1.0000 |
| 1 | LS4_H5_EXIT_RISK05 | top20_2022_trials | 6,142.0000 | 0.3173 | 1.8085 | 1.1866 | 0.9424 |
| 2 | LS4_H5_EXIT_RISK05 | all_trials | 14,174.0000 | 0.3173 | 1.8085 | 1.2517 | 0.9207 |

## White Reality Check

One-sided stationary bootstrap for the best candidate mean. Against BTC the test
uses daily excess returns over BTC buy-and-hold. It covers only this family's
return series; earlier families kept no daily returns, so their selection is
priced by the project-scope Deflated Sharpe instead.

| index | benchmark | observed_max_mean_daily | reality_check_p_value | bootstrap_count |
| --- | --- | --- | --- | --- |
| 0 | zero | 0.0021 | 0.0040 | 1,000.0000 |
| 1 | BTC buy-and-hold | 0.0014 | 0.0190 | 1,000.0000 |

## CSCV / PBO

- PBO: 0.0065 (logit rule, lower is better)
- Median out-of-sample logit of the in-sample winner: 0.6931
- CSCV combinations: 924; rows used: 1724
- Most frequently selected candidate: `LS4_H5_EXIT_RISK05`

PBO judges the procedure "pick the best full-sample candidate". The fixed primary
was itself chosen with the full sample in view, so a PBO above 0.5 is evidence
against trusting the family's in-sample ranking, including the primary's place in it.
