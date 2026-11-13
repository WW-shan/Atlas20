# PR2026-11-LS93-LS92-ROBUSTNESS

LS93 is a frozen robustness and attribution audit of LS92. It does not re-fit weights,
scan parameters, change the live track, or send orders.

## Scenario summary

| index | cost_bps | candidate | baseline | common_start | common_end | common_rows | candidate_full_multiple | baseline_full_multiple | candidate_full_sharpe | baseline_full_sharpe | candidate_full_max_drawdown | baseline_full_max_drawdown | candidate_validation_multiple | baseline_validation_multiple | candidate_validation_sharpe | baseline_validation_sharpe | candidate_validation_max_drawdown | baseline_validation_max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | LS92 | LS57 | 2022-01-01 00:00:00+00:00 | 2026-09-20 00:00:00+00:00 | 1,724.0000 | 68.7216 | 65.6712 | 1.9797 | 1.9638 | -0.3837 | -0.3896 | 15.4108 | 14.9011 | 2.1078 | 2.0925 | -0.3186 | -0.3318 |
| 1 | 20.0000 | LS91 | LS57 | 2022-01-01 00:00:00+00:00 | 2026-09-20 00:00:00+00:00 | 1,724.0000 | 60.0002 | 58.2059 | 1.9242 | 1.9143 | -0.3928 | -0.3983 | 14.1470 | 13.8153 | 2.0505 | 2.0417 | -0.3336 | -0.3452 |

## Daily excess diagnostics

| index | cost_bps | scenario | years_outperforming | years_total | best_year_excess_multiple | worst_year_excess_multiple | worst_leave_one_year_excess_multiple | worst_leave_one_year_excess_sharpe | rolling_365_windows | rolling_365_outperform_share | worst_rolling_365_excess_multiple | median_rolling_365_excess_multiple | mean_daily_excess | annualized_excess_sharpe | newey_west_t_63 | bootstrap_probability_positive | bootstrap_total_log_excess_ci_2_5 | bootstrap_total_log_excess_median | bootstrap_total_log_excess_ci_97_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 13.0164bps | 3.0000 | 5.0000 | 0.1930 | -0.0598 | -0.1990 | -0.0051 | 1,359.0000 | 0.6770 | -0.0797 | 0.0160 | 0.0000 | 0.4612 | 0.9435 | 0.8178 | -0.0528 | 0.0449 | 0.1458 |
| 1 | 20.0000 | 20bps | 2.0000 | 5.0000 | 0.1770 | -0.0681 | -0.5124 | -0.0121 | 1,359.0000 | 0.6475 | -0.0896 | 0.0111 | 0.0000 | 0.3168 | 0.6483 | 0.7300 | -0.0672 | 0.0298 | 0.1304 |

## Rolling 365D diagnostics

| index | cost_bps | rolling_365_windows | rolling_365_outperform_share | worst_rolling_365_excess_multiple | median_rolling_365_excess_multiple | worst_rolling_365_excess_sharpe | median_rolling_365_excess_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 1,359.0000 | 0.6770 | -0.0797 | 0.0160 | -0.1590 | 0.0134 |
| 1 | 20.0000 | 1,359.0000 | 0.6475 | -0.0896 | 0.0111 | -0.1751 | 0.0078 |

## Yearly comparison

| index | cost_bps | year | candidate_multiple | candidate_cagr | candidate_sharpe | candidate_max_drawdown | baseline_multiple | baseline_cagr | baseline_sharpe | baseline_max_drawdown | scenario | excess_multiple | excess_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 2,022.0000 | 1.1086 | 0.1089 | 0.6176 | -0.1292 | 1.1508 | 0.1513 | 0.7763 | -0.1354 | 13.0164bps | -0.0423 | -0.1587 |
| 1 | 13.0164 | 2,023.0000 | 4.0226 | 3.0380 | 2.4700 | -0.3837 | 3.8296 | 2.8437 | 2.3945 | -0.3896 | 13.0164bps | 0.1930 | 0.0755 |
| 2 | 13.0164 | 2,024.0000 | 2.1051 | 1.1051 | 1.5529 | -0.3186 | 1.9994 | 0.9994 | 1.4717 | -0.3318 | 13.0164bps | 0.1056 | 0.0813 |
| 3 | 13.0164 | 2,025.0000 | 2.9615 | 1.9704 | 2.1774 | -0.1848 | 3.0213 | 2.0305 | 2.2180 | -0.1786 | 13.0164bps | -0.0598 | -0.0407 |
| 4 | 13.0164 | 2,026.0000 | 2.4719 | 2.5282 | 3.0659 | -0.1450 | 2.4667 | 2.5177 | 3.0622 | -0.1453 | 13.0164bps | 0.0053 | 0.0037 |
| 5 | 20.0000 | 2,022.0000 | 1.0902 | 0.0904 | 0.5332 | -0.1344 | 1.1346 | 0.1350 | 0.7081 | -0.1397 | 20bps | -0.0444 | -0.1749 |
| 6 | 20.0000 | 2,023.0000 | 3.8903 | 2.9049 | 2.4172 | -0.3928 | 3.7133 | 2.7267 | 2.3457 | -0.3983 | 20bps | 0.1770 | 0.0715 |
| 7 | 20.0000 | 2,024.0000 | 2.0303 | 1.0303 | 1.4911 | -0.3336 | 1.9360 | 0.9360 | 1.4161 | -0.3452 | 20bps | 0.0943 | 0.0750 |
| 8 | 20.0000 | 2,025.0000 | 2.8687 | 1.8770 | 2.1223 | -0.1852 | 2.9368 | 1.9455 | 2.1692 | -0.1790 | 20bps | -0.0681 | -0.0469 |
| 9 | 20.0000 | 2,026.0000 | 2.4290 | 2.4431 | 3.0111 | -0.1480 | 2.4299 | 2.4448 | 3.0153 | -0.1477 | 20bps | -0.0009 | -0.0042 |

## Leave-one-year-out

| index | cost_bps | scenario | excluded_year | candidate_multiple | baseline_multiple | excess_multiple | candidate_sharpe | baseline_sharpe | excess_sharpe | candidate_max_drawdown | baseline_max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 13.0164bps | 2,022.0000 | 61.9916 | 57.0647 | 4.9269 | 2.2106 | 2.1772 | 0.0334 | -0.3837 | -0.3896 |
| 1 | 13.0164 | 13.0164bps | 2,023.0000 | 17.0839 | 17.1485 | -0.0646 | 1.8270 | 1.8321 | -0.0051 | -0.3186 | -0.3318 |
| 2 | 13.0164 | 13.0164bps | 2,024.0000 | 32.6456 | 32.8447 | -0.1990 | 2.1203 | 2.1231 | -0.0028 | -0.3837 | -0.3896 |
| 3 | 13.0164 | 13.0164bps | 2,025.0000 | 23.2046 | 21.7359 | 1.4687 | 1.9234 | 1.8901 | 0.0333 | -0.3837 | -0.3896 |
| 4 | 13.0164 | 13.0164bps | 2,026.0000 | 27.8006 | 26.6235 | 1.1771 | 1.8216 | 1.8036 | 0.0180 | -0.3837 | -0.3896 |
| 5 | 20.0000 | 20bps | 2,022.0000 | 55.0366 | 51.3003 | 3.7363 | 2.1548 | 2.1271 | 0.0276 | -0.3928 | -0.3983 |
| 6 | 20.0000 | 20bps | 2,023.0000 | 15.4228 | 15.6750 | -0.2521 | 1.7698 | 1.7819 | -0.0121 | -0.3336 | -0.3452 |
| 7 | 20.0000 | 20bps | 2,024.0000 | 29.5530 | 30.0654 | -0.5124 | 2.0666 | 2.0754 | -0.0088 | -0.3928 | -0.3983 |
| 8 | 20.0000 | 20bps | 2,025.0000 | 20.9155 | 19.8194 | 1.0962 | 1.8676 | 1.8404 | 0.0272 | -0.3928 | -0.3983 |
| 9 | 20.0000 | 20bps | 2,026.0000 | 24.7016 | 23.9544 | 0.7472 | 1.7658 | 1.7537 | 0.0122 | -0.3928 | -0.3983 |

## Sleeve contributions

| index | cost_bps | candidate | sleeve | weight | terminal_multiple | terminal_multiple_contribution | wealth_share | excess_vs_baseline | excess_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | LS92 | LS57 | 0.5000 | 65.6712 | 32.8356 | 0.4778 | 0.0000 | 0.0000 |
| 1 | 13.0164 | LS92 | LS82_CARRY | 0.2500 | 73.0767 | 18.2692 | 0.2658 | 1.8514 | 0.6069 |
| 2 | 13.0164 | LS92 | LS88_LONG_CARRY | 0.2500 | 70.4673 | 17.6168 | 0.2564 | 1.1990 | 0.3931 |
| 3 | 13.0164 | LS92 | LS89_MA21 | 0.0000 | 61.7783 | 0.0000 | 0.0000 | -0.0000 | -0.0000 |
| 4 | 20.0000 | LS91 | LS57 | 0.5000 | 58.2059 | 29.1030 | 0.4850 | 0.0000 | 0.0000 |
| 5 | 20.0000 | LS91 | LS82_CARRY | 0.2500 | 62.1228 | 15.5307 | 0.2588 | 0.9792 | 0.5457 |
| 6 | 20.0000 | LS91 | LS88_LONG_CARRY | 0.2500 | 61.4661 | 15.3665 | 0.2561 | 0.8151 | 0.4543 |
| 7 | 20.0000 | LS91 | LS89_MA21 | 0.0000 | 54.7231 | 0.0000 | 0.0000 | -0.0000 | -0.0000 |

## Correlations

| index | cost_bps | strategy_left | strategy_right | correlation |
| --- | --- | --- | --- | --- |
| 0 | 13.0164 | LS57 | LS57 | 1.0000 |
| 1 | 13.0164 | LS57 | LS82_CARRY | 0.9953 |
| 2 | 13.0164 | LS57 | LS88_LONG_CARRY | 0.9934 |
| 3 | 13.0164 | LS57 | LS89_MA21 | 0.9835 |
| 4 | 13.0164 | LS82_CARRY | LS57 | 0.9953 |
| 5 | 13.0164 | LS82_CARRY | LS82_CARRY | 1.0000 |
| 6 | 13.0164 | LS82_CARRY | LS88_LONG_CARRY | 0.9912 |
| 7 | 13.0164 | LS82_CARRY | LS89_MA21 | 0.9785 |
| 8 | 13.0164 | LS88_LONG_CARRY | LS57 | 0.9934 |
| 9 | 13.0164 | LS88_LONG_CARRY | LS82_CARRY | 0.9912 |
| 10 | 13.0164 | LS88_LONG_CARRY | LS88_LONG_CARRY | 1.0000 |
| 11 | 13.0164 | LS88_LONG_CARRY | LS89_MA21 | 0.9741 |
| 12 | 13.0164 | LS89_MA21 | LS57 | 0.9835 |
| 13 | 13.0164 | LS89_MA21 | LS82_CARRY | 0.9785 |
| 14 | 13.0164 | LS89_MA21 | LS88_LONG_CARRY | 0.9741 |
| 15 | 13.0164 | LS89_MA21 | LS89_MA21 | 1.0000 |
| 16 | 20.0000 | LS57 | LS57 | 1.0000 |
| 17 | 20.0000 | LS57 | LS82_CARRY | 0.9953 |
| 18 | 20.0000 | LS57 | LS88_LONG_CARRY | 0.9934 |
| 19 | 20.0000 | LS57 | LS89_MA21 | 0.9835 |
| 20 | 20.0000 | LS82_CARRY | LS57 | 0.9953 |
| 21 | 20.0000 | LS82_CARRY | LS82_CARRY | 1.0000 |
| 22 | 20.0000 | LS82_CARRY | LS88_LONG_CARRY | 0.9911 |
| 23 | 20.0000 | LS82_CARRY | LS89_MA21 | 0.9784 |
| 24 | 20.0000 | LS88_LONG_CARRY | LS57 | 0.9934 |
| 25 | 20.0000 | LS88_LONG_CARRY | LS82_CARRY | 0.9911 |
| 26 | 20.0000 | LS88_LONG_CARRY | LS88_LONG_CARRY | 1.0000 |
| 27 | 20.0000 | LS88_LONG_CARRY | LS89_MA21 | 0.9741 |
| 28 | 20.0000 | LS89_MA21 | LS57 | 0.9835 |
| 29 | 20.0000 | LS89_MA21 | LS82_CARRY | 0.9784 |
| 30 | 20.0000 | LS89_MA21 | LS88_LONG_CARRY | 0.9741 |
| 31 | 20.0000 | LS89_MA21 | LS89_MA21 | 1.0000 |

## Multiple-testing diagnostics

### Deflated Sharpe

| index | cost_bps | candidate | scope | trial_count | trial_sharpe_std_annualized | observed_sharpe | expected_max_sharpe | deflated_sharpe_probability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | LS92 | family | 5.0000 | 0.0231 | 1.9792 | 0.0276 | 1.0000 |
| 1 | 13.0164 | LS92 | top20_2022_trials | 6,201.0000 | 0.4821 | 1.9792 | 1.8040 | 0.6705 |
| 2 | 13.0164 | LS92 | all_trials | 14,410.0000 | 0.4821 | 1.9792 | 1.9037 | 0.5754 |
| 3 | 13.0164 | LS57 | family | 5.0000 | 0.0231 | 1.9632 | 0.0276 | 1.0000 |
| 4 | 13.0164 | LS57 | top20_2022_trials | 6,201.0000 | 0.4821 | 1.9632 | 1.8040 | 0.6557 |
| 5 | 13.0164 | LS57 | all_trials | 14,410.0000 | 0.4821 | 1.9632 | 1.9037 | 0.5595 |
| 6 | 20.0000 | LS91 | family | 5.0000 | 0.0173 | 1.9237 | 0.0206 | 1.0000 |
| 7 | 20.0000 | LS91 | top20_2022_trials | 6,201.0000 | 0.4821 | 1.9237 | 1.8040 | 0.6181 |
| 8 | 20.0000 | LS91 | all_trials | 14,410.0000 | 0.4821 | 1.9237 | 1.9037 | 0.5200 |
| 9 | 20.0000 | LS57 | family | 5.0000 | 0.0173 | 1.9138 | 0.0206 | 1.0000 |
| 10 | 20.0000 | LS57 | top20_2022_trials | 6,201.0000 | 0.4821 | 1.9138 | 1.8040 | 0.6085 |
| 11 | 20.0000 | LS57 | all_trials | 14,410.0000 | 0.4821 | 1.9138 | 1.9037 | 0.5101 |

### CSCV / PBO

| index | cost_bps | pbo | median_oos_logit | cscv_combinations | rows_used | most_selected_candidate | most_selected_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | 0.4892 | 0.6931 | 924.0000 | 1,724.0000 | LS82_CARRY | 613.0000 |
| 1 | 20.0000 | 0.6515 | -0.6931 | 924.0000 | 1,724.0000 | LS82_CARRY | 551.0000 |

### Reality Check

| index | cost_bps | benchmark | observed_max_mean_daily | reality_check_p_value | bootstrap_count |
| --- | --- | --- | --- | --- | --- |
| 0 | 13.0164 | zero | 0.0028 | 0.0030 | 5,000.0000 |
| 1 | 13.0164 | LS57 excess | 0.0001 | 0.4891 | 5,000.0000 |
| 2 | 20.0000 | zero | 0.0028 | 0.0034 | 5,000.0000 |
| 3 | 20.0000 | LS57 excess | 0.0000 | 0.5613 | 5,000.0000 |

## Evidence classification

**inconclusive**

- 13.0164bps: candidate 68.7216x vs baseline 65.6712x; bootstrap 2.5% -5.28%; years 3/5; worst leave-one-year excess -0.1990x
- 20bps: candidate 60.0002x vs baseline 58.2059x; bootstrap 2.5% -6.72%; years 2/5; worst leave-one-year excess -0.5124x
- incremental concentration 60.7%; the remaining evidence is evaluated in the PBO, Reality Check and project-wide DSR tables above.

The label describes the frozen evidence only. It does not promote LS92 or change the live
track; the next research branch continues regardless of the label.

Research output only; no orders sent.
