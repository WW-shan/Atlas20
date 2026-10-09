# How much out-of-sample data closes the Deflated-Sharpe gap?

Series: `PR2026-10-H5|h3_day_close|20` in `reports/phase_momentum_hypotheses_2026_10/returns_20bps.csv` (1725 days).
Scope: `top20_2022_trials` with N = 6,138 trials; expected-maximum Sharpe 1.184 annualized.
In-sample annualized Sharpe 1.623, DSR 0.858 (target 0.95).

The OOS block is a counterfactual: the same return shape, a different mean.
It is not a forecast, and it selects nothing.

## DSR if new data earns exactly the in-sample Sharpe

| index | oos_days | total_days | oos_annualized_sharpe | combined_annualized_sharpe | dsr |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.0000 | 1,725.0000 | 1.6231 | 1.6231 | 0.8580 |
| 1 | 30.0000 | 1,755.0000 | 1.6231 | 1.6231 | 0.8600 |
| 2 | 90.0000 | 1,815.0000 | 1.6231 | 1.6231 | 0.8641 |
| 3 | 180.0000 | 1,905.0000 | 1.6231 | 1.6231 | 0.8699 |
| 4 | 365.0000 | 2,090.0000 | 1.6231 | 1.6231 | 0.8808 |
| 5 | 730.0000 | 2,455.0000 | 1.6231 | 1.6231 | 0.8994 |
| 6 | 1,095.0000 | 2,820.0000 | 1.6231 | 1.6231 | 0.9146 |

## Out-of-sample Sharpe needed at a fixed horizon

| index | oos_days | oos_years | required_oos_annualized_sharpe | multiplier_vs_in_sample |
| --- | --- | --- | --- | --- |
| 0 | 30.0000 | 0.0822 | 15.0346 | 9.2626 |
| 1 | 90.0000 | 0.2466 | 5.9112 | 3.6418 |
| 2 | 180.0000 | 0.4932 | 3.6999 | 2.2794 |
| 3 | 365.0000 | 1.0000 | 2.5839 | 1.5919 |
| 4 | 730.0000 | 2.0000 | 2.0337 | 1.2529 |
| 5 | 1,095.0000 | 3.0000 | 1.8435 | 1.1357 |

## Days needed at an assumed out-of-sample Sharpe

| index | assumed_oos_annualized_sharpe | required_oos_days | required_oos_years |
| --- | --- | --- | --- |
| 0 | 0.8000 |  |  |
| 1 | 1.0000 |  |  |
| 2 | 1.2000 |  |  |
| 3 | 1.4000 |  |  |
| 4 | 1.6000 | 2,618.5000 | 7.1740 |
| 5 | 1.8000 | 1,231.5000 | 3.3740 |
| 6 | 2.0000 | 776.5000 | 2.1274 |

## Contrast: an out-of-sample-only test is far cheaper than the DSR

The DSR re-pays the selection penalty on the whole sample. A test that uses
only data collected after the freeze does not: that window never selected
the specification, so its Sharpe is an unbiased estimate. The table below
is the one-sided t-test on the OOS Sharpe alone (`t = SR * sqrt(years)`).

| index | assumed_oos_annualized_sharpe | days_to_95%_t_test | years_to_95%_t_test | days_to_99%_t_test | years_to_99%_t_test |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.8000 | 1,543.0923 | 4.2277 | 3,086.3440 | 8.4557 |
| 1 | 1.0000 | 987.5790 | 2.7057 | 1,975.2602 | 5.4117 |
| 2 | 1.2000 | 685.8188 | 1.8790 | 1,371.7084 | 3.7581 |
| 3 | 1.4000 | 503.8669 | 1.3805 | 1,007.7858 | 2.7611 |
| 4 | 1.6000 | 385.7731 | 1.0569 | 771.5860 | 2.1139 |
| 5 | 1.8000 | 304.8083 | 0.8351 | 609.6482 | 1.6703 |
| 6 | 2.0000 | 246.8948 | 0.6764 | 493.8150 | 1.3529 |

For reference the in-sample annualized Sharpe is 1.623.
