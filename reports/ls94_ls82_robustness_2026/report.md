# PR2026-11-LS94-LS82-ROBUSTNESS

LS94 is a frozen robustness audit of LS82. It does not change the carry rules, allocation,
funding, execution, live track, or send orders.

## Scenario summary

| index | cost_bps | candidate | baseline | common_start | common_end | common_rows | candidate_full_multiple | baseline_full_multiple | candidate_full_sharpe | baseline_full_sharpe | candidate_full_max_drawdown | baseline_full_max_drawdown | candidate_validation_multiple | baseline_validation_multiple | candidate_validation_sharpe | baseline_validation_sharpe | candidate_validation_max_drawdown | baseline_validation_max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | LS82 | LS57 | 2022-01-01 00:00:00+00:00 | 2026-09-20 00:00:00+00:00 | 1,724.0000 | 73.0767 | 65.6712 | 2.0189 | 1.9638 | -0.3700 | -0.3896 | 16.1532 | 14.9011 | 2.1621 | 2.0925 | -0.2887 | -0.3318 |
| 1 | 20.0000 | LS82 | LS57 | 2022-01-01 00:00:00+00:00 | 2026-09-20 00:00:00+00:00 | 1,724.0000 | 62.1228 | 58.2059 | 1.9519 | 1.9143 | -0.3798 | -0.3983 | 14.5712 | 13.8153 | 2.0921 | 2.0417 | -0.3001 | -0.3452 |

## Daily excess diagnostics

| index | cost_bps | scenario | years_outperforming | years_total | best_year_excess_multiple | worst_year_excess_multiple | worst_leave_one_year_excess_multiple | worst_leave_one_year_excess_sharpe | rolling_365_windows | rolling_365_outperform_share | worst_rolling_365_excess_multiple | median_rolling_365_excess_multiple | mean_daily_excess | annualized_excess_sharpe | newey_west_t_63 | bootstrap_probability_positive | bootstrap_total_log_excess_ci_2_5 | bootstrap_total_log_excess_median | bootstrap_total_log_excess_ci_97_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 13.0164bps | 3.0000 | 5.0000 | 0.3788 | -0.1165 | 0.2161 | 0.0155 | 1,359.0000 | 0.7035 | -0.3158 | 0.0387 | 0.0001 | 0.4186 | 0.9414 | 0.8402 | -0.0981 | 0.1053 | 0.3175 |
| 1 | 20.0000 | 20bps | 3.0000 | 5.0000 | 0.3373 | -0.1424 | -0.6806 | -0.0043 | 1,359.0000 | 0.6372 | -0.3696 | 0.0250 | 0.0000 | 0.2408 | 0.5404 | 0.7336 | -0.1407 | 0.0636 | 0.2760 |

## Rolling 365D diagnostics

| index | cost_bps | rolling_365_windows | rolling_365_outperform_share | worst_rolling_365_excess_multiple | median_rolling_365_excess_multiple | worst_rolling_365_excess_sharpe | median_rolling_365_excess_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 1,359.0000 | 0.7035 | -0.3158 | 0.0387 | -0.3362 | 0.0610 |
| 1 | 20.0000 | 1,359.0000 | 0.6372 | -0.3696 | 0.0250 | -0.3650 | 0.0447 |

## Yearly comparison

| index | cost_bps | year | candidate_multiple | candidate_cagr | candidate_sharpe | candidate_max_drawdown | baseline_multiple | baseline_cagr | baseline_sharpe | baseline_max_drawdown | scenario | excess_multiple | excess_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 2,022.0000 | 1.0750 | 0.0752 | 0.4406 | -0.1457 | 1.1508 | 0.1513 | 0.7763 | -0.1354 | 13.0164bps | -0.0758 | -0.3357 |
| 1 | 13.0164 | 2,023.0000 | 4.2084 | 3.2250 | 2.5624 | -0.3700 | 3.8296 | 2.8437 | 2.3945 | -0.3896 | 13.0164bps | 0.3788 | 0.1679 |
| 2 | 13.0164 | 2,024.0000 | 2.2070 | 1.2070 | 1.6439 | -0.2887 | 1.9994 | 0.9994 | 1.4717 | -0.3318 | 13.0164bps | 0.2076 | 0.1723 |
| 3 | 13.0164 | 2,025.0000 | 2.9048 | 1.9133 | 2.1831 | -0.1904 | 3.0213 | 2.0305 | 2.2180 | -0.1786 | 13.0164bps | -0.1165 | -0.0350 |
| 4 | 13.0164 | 2,026.0000 | 2.5196 | 2.6234 | 3.1273 | -0.1462 | 2.4667 | 2.5177 | 3.0622 | -0.1453 | 13.0164bps | 0.0530 | 0.0651 |
| 5 | 20.0000 | 2,022.0000 | 1.0525 | 0.0527 | 0.3436 | -0.1524 | 1.1346 | 0.1350 | 0.7081 | -0.1397 | 20bps | -0.0821 | -0.3645 |
| 6 | 20.0000 | 2,023.0000 | 4.0506 | 3.0662 | 2.5016 | -0.3798 | 3.7133 | 2.7267 | 2.3457 | -0.3983 | 20bps | 0.3373 | 0.1559 |
| 7 | 20.0000 | 2,024.0000 | 2.1141 | 1.1141 | 1.5698 | -0.3001 | 1.9360 | 0.9360 | 1.4161 | -0.3452 | 20bps | 0.1781 | 0.1538 |
| 8 | 20.0000 | 2,025.0000 | 2.7944 | 1.8023 | 2.1144 | -0.1951 | 2.9368 | 1.9455 | 2.1692 | -0.1790 | 20bps | -0.1424 | -0.0548 |
| 9 | 20.0000 | 2,026.0000 | 2.4665 | 2.5173 | 3.0602 | -0.1502 | 2.4299 | 2.4448 | 3.0153 | -0.1477 | 20bps | 0.0366 | 0.0449 |

## Leave-one-year-out

| index | cost_bps | scenario | excluded_year | candidate_multiple | baseline_multiple | excess_multiple | candidate_sharpe | baseline_sharpe | excess_sharpe | candidate_max_drawdown | baseline_max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 13.0164bps | 2,022.0000 | 67.9789 | 57.0647 | 10.9142 | 2.2761 | 2.1772 | 0.0989 | -0.3700 | -0.3896 |
| 1 | 13.0164 | 13.0164bps | 2,023.0000 | 17.3645 | 17.1485 | 0.2161 | 1.8477 | 1.8321 | 0.0155 | -0.2887 | -0.3318 |
| 2 | 13.0164 | 13.0164bps | 2,024.0000 | 33.1113 | 32.8447 | 0.2666 | 2.1432 | 2.1231 | 0.0201 | -0.3700 | -0.3896 |
| 3 | 13.0164 | 13.0164bps | 2,025.0000 | 25.1572 | 21.7359 | 3.4213 | 1.9727 | 1.8901 | 0.0826 | -0.3700 | -0.3896 |
| 4 | 13.0164 | 13.0164bps | 2,026.0000 | 29.0028 | 26.6235 | 2.3792 | 1.8555 | 1.8036 | 0.0519 | -0.3700 | -0.3896 |
| 5 | 20.0000 | 20bps | 2,022.0000 | 59.0218 | 51.3003 | 7.7215 | 2.2091 | 2.1271 | 0.0820 | -0.3798 | -0.3983 |
| 6 | 20.0000 | 20bps | 2,023.0000 | 15.3368 | 15.6750 | -0.3382 | 1.7776 | 1.7819 | -0.0043 | -0.3001 | -0.3452 |
| 7 | 20.0000 | 20bps | 2,024.0000 | 29.3848 | 30.0654 | -0.6806 | 2.0782 | 2.0754 | 0.0028 | -0.3798 | -0.3983 |
| 8 | 20.0000 | 20bps | 2,025.0000 | 22.2312 | 19.8194 | 2.4118 | 1.9060 | 1.8404 | 0.0656 | -0.3798 | -0.3983 |
| 9 | 20.0000 | 20bps | 2,026.0000 | 25.1868 | 23.9544 | 1.2325 | 1.7883 | 1.7537 | 0.0346 | -0.3798 | -0.3983 |

## Multiple-testing diagnostics

### Deflated Sharpe

| index | cost_bps | candidate | scope | trial_count | trial_sharpe_std_annualized | observed_sharpe | expected_max_sharpe | deflated_sharpe_probability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | LS82 | family | 2.0000 | 0.0390 | 2.0183 | 0.0203 | 1.0000 |
| 1 | 13.0164 | LS82 | top20_2022_trials | 6,201.0000 | 0.4821 | 2.0183 | 1.8040 | 0.7058 |
| 2 | 13.0164 | LS82 | all_trials | 14,411.0000 | 0.4821 | 2.0183 | 1.9037 | 0.6138 |
| 3 | 13.0164 | LS57 | family | 2.0000 | 0.0390 | 1.9632 | 0.0203 | 1.0000 |
| 4 | 13.0164 | LS57 | top20_2022_trials | 6,201.0000 | 0.4821 | 1.9632 | 1.8040 | 0.6557 |
| 5 | 13.0164 | LS57 | all_trials | 14,411.0000 | 0.4821 | 1.9632 | 1.9037 | 0.5595 |
| 6 | 20.0000 | LS82 | family | 2.0000 | 0.0266 | 1.9513 | 0.0138 | 1.0000 |
| 7 | 20.0000 | LS82 | top20_2022_trials | 6,201.0000 | 0.4821 | 1.9513 | 1.8040 | 0.6444 |
| 8 | 20.0000 | LS82 | all_trials | 14,411.0000 | 0.4821 | 1.9513 | 1.9037 | 0.5477 |
| 9 | 20.0000 | LS57 | family | 2.0000 | 0.0266 | 1.9138 | 0.0138 | 1.0000 |
| 10 | 20.0000 | LS57 | top20_2022_trials | 6,201.0000 | 0.4821 | 1.9138 | 1.8040 | 0.6085 |
| 11 | 20.0000 | LS57 | all_trials | 14,411.0000 | 0.4821 | 1.9138 | 1.9037 | 0.5101 |

### CSCV / PBO

| index | cost_bps | pbo | median_oos_logit | cscv_combinations | rows_used | most_selected_candidate | most_selected_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 0.3052 | 0.6931 | 924.0000 | 1,724.0000 | LS82 | 783.0000 |
| 1 | 20.0000 | 0.5108 | -0.6931 | 924.0000 | 1,724.0000 | LS82 | 688.0000 |

### Reality Check

| index | cost_bps | benchmark | observed_max_mean_daily | reality_check_p_value | bootstrap_count |
| --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | zero | 0.0028 | 0.0012 | 5,000.0000 |
| 1 | 13.0164 | LS57 excess | 0.0001 | 0.1834 | 5,000.0000 |
| 2 | 20.0000 | zero | 0.0027 | 0.0018 | 5,000.0000 |
| 3 | 20.0000 | LS57 excess | 0.0000 | 0.2995 | 5,000.0000 |

## Evidence classification

**year-concentrated**

- 13.0164bps: LS82 73.0767x vs LS57 65.6712x; bootstrap 2.5% -9.81%; years 3/5; worst leave-one-year excess +0.2161x; PBO 0.3052; RC vs LS57 p=0.1834
- 20bps: LS82 62.1228x vs LS57 58.2059x; bootstrap 2.5% -14.07%; years 3/5; worst leave-one-year excess -0.6806x; PBO 0.5108; RC vs LS57 p=0.2995

The label describes frozen evidence only. It does not promote LS82 or change the live track;
the next research branch continues regardless of the label.

Research output only; no orders sent.
