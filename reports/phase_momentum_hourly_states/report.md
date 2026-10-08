# Do intraday (hourly) states mark PR2026-10-H5's bad months?

Hypothesis generation only: no rule was changed, no trial was registered.
Months: 57; crash months (return <= -8%): 10.

These states come from Binance hourly candles and cannot be built from the daily
panel the strategy already sees. They are read at the last close before each month
and compared with that month's net 20 bps return and its BTC return; the decisive
column is `excess`, because the failure mode is market up and strategy down.

## Pre-declared bar (family-wise over both screens)

`|Spearman(state, excess)| >= 0.38` - the 5% two-sided level divided by the
eighteen candidate states of Section 00.15 and this section - plus monotone terciles
and `|diff_over_rest_std| >= 0.50`.

## Point-in-time Top20 coverage of the hourly feed

| index | metric | value |
| --- | --- | --- |
| 0 | hourly pairs loaded | 56.0000 |
| 1 | distinct point-in-time members | 53.0000 |
| 2 | members without hourly data | 1.0000 |
| 3 | member-days observed | 34,381.0000 |
| 4 | member-days total | 34,500.0000 |
| 5 | member-day coverage | 0.9966 |

## Crash versus rest

| index | crash_mean | rest_mean | difference | rest_std | diff_over_rest_std | welch_t | crash_months |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rv_ratio | 1.1762 | 1.0193 | 0.1569 | 0.6252 | 0.2510 | 0.5647 | 9.0000 |
| range_ratio | 1.0115 | 0.9545 | 0.0570 | 0.2499 | 0.2281 | 0.5693 | 9.0000 |
| rvs_down_share | 0.4980 | 0.5170 | -0.0190 | 0.0540 | -0.3518 | -1.1523 | 10.0000 |
| hour_share_ratio | 0.9913 | 1.0205 | -0.0292 | 0.0889 | -0.3283 | -0.8778 | 9.0000 |
| venue_share_ratio | 0.9644 | 0.9758 | -0.0114 | 0.2664 | -0.0428 | -0.1405 | 9.0000 |
| hourly_autocorr | -0.0147 | -0.0134 | -0.0013 | 0.0429 | -0.0295 | -0.1366 | 10.0000 |
| night_minus_day | 0.0193 | 0.0004 | 0.0189 | 0.0817 | 0.2308 | 0.8359 | 10.0000 |

## Rank information against next-month excess return

| index | observations | spearman | p_value |
| --- | --- | --- | --- |
| rv_ratio | 53.0000 | 0.0359 | 0.7976 |
| range_ratio | 53.0000 | 0.0808 | 0.5627 |
| rvs_down_share | 57.0000 | -0.1832 | 0.1669 |
| hour_share_ratio | 53.0000 | 0.2620 | 0.0526 |
| venue_share_ratio | 53.0000 | -0.1774 | 0.1980 |
| hourly_autocorr | 57.0000 | -0.0433 | 0.7479 |
| night_minus_day | 57.0000 | 0.1233 | 0.3569 |

## Excess return by state tercile (1 = lowest state, 3 = highest)

| index | state | bucket | months | mean_ret | mean_btc | mean_excess | hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | rv_ratio | 1.0000 | 18.0000 | 0.0695 | 0.0601 | 0.0094 | 0.3889 |
| 1 | rv_ratio | 2.0000 | 17.0000 | 0.1394 | 0.0669 | 0.0725 | 0.6471 |
| 2 | rv_ratio | 3.0000 | 18.0000 | 0.0167 | -0.0424 | 0.0590 | 0.2222 |
| 3 | range_ratio | 1.0000 | 18.0000 | 0.0913 | 0.0685 | 0.0228 | 0.5000 |
| 4 | range_ratio | 2.0000 | 17.0000 | 0.0917 | 0.0689 | 0.0228 | 0.5294 |
| 5 | range_ratio | 3.0000 | 18.0000 | 0.0398 | -0.0527 | 0.0925 | 0.2222 |
| 6 | rvs_down_share | 1.0000 | 19.0000 | 0.0894 | 0.0189 | 0.0705 | 0.5263 |
| 7 | rvs_down_share | 2.0000 | 19.0000 | 0.0973 | 0.0184 | 0.0788 | 0.4211 |
| 8 | rvs_down_share | 3.0000 | 19.0000 | 0.0159 | 0.0307 | -0.0148 | 0.2632 |
| 9 | hour_share_ratio | 1.0000 | 18.0000 | 0.0694 | 0.0716 | -0.0022 | 0.4444 |
| 10 | hour_share_ratio | 2.0000 | 17.0000 | 0.0724 | 0.0096 | 0.0627 | 0.4706 |
| 11 | hour_share_ratio | 3.0000 | 18.0000 | 0.0800 | 0.0002 | 0.0798 | 0.3333 |
| 12 | venue_share_ratio | 1.0000 | 18.0000 | 0.1272 | 0.0393 | 0.0879 | 0.6111 |
| 13 | venue_share_ratio | 2.0000 | 17.0000 | 0.0469 | -0.0089 | 0.0558 | 0.2353 |
| 14 | venue_share_ratio | 3.0000 | 18.0000 | 0.0464 | 0.0501 | -0.0037 | 0.3889 |
| 15 | hourly_autocorr | 1.0000 | 19.0000 | 0.1077 | 0.0382 | 0.0696 | 0.4211 |
| 16 | hourly_autocorr | 2.0000 | 19.0000 | 0.0536 | -0.0006 | 0.0542 | 0.4737 |
| 17 | hourly_autocorr | 3.0000 | 19.0000 | 0.0413 | 0.0305 | 0.0108 | 0.3158 |
| 18 | night_minus_day | 1.0000 | 19.0000 | 0.0352 | 0.0073 | 0.0279 | 0.3684 |
| 19 | night_minus_day | 2.0000 | 19.0000 | 0.1218 | 0.0849 | 0.0370 | 0.6316 |
| 20 | night_minus_day | 3.0000 | 19.0000 | 0.0455 | -0.0241 | 0.0696 | 0.2105 |

## Correlation with the states H5 already carries

| index | gate_open_before | breadth_before | disp_ratio_before | mkt_vol_before | own63_before | gross_before |
| --- | --- | --- | --- | --- | --- | --- |
| rv_ratio | -0.0124 | 0.0919 | 0.4461 | 0.0033 | 0.3156 | -0.1165 |
| range_ratio | 0.0025 | 0.0577 | 0.3727 | -0.0722 | 0.2920 | -0.0869 |
| rvs_down_share | -0.1773 | -0.3988 | -0.1971 | 0.1029 | -0.1189 | -0.1176 |
| hour_share_ratio | -0.4782 | -0.3393 | -0.0969 | 0.1169 | -0.4773 | -0.4201 |
| venue_share_ratio | -0.1611 | 0.1295 | 0.2960 | 0.0631 | 0.0954 | -0.1848 |
| hourly_autocorr | -0.2584 | -0.2597 | -0.1063 | 0.0598 | -0.0292 | -0.3219 |
| night_minus_day | 0.0000 | -0.0610 | -0.0527 | -0.0043 | 0.0360 | 0.0729 |

## Verdicts

| index | spearman | abs_spearman | ic_bar | separation_bar | passes_ic_bar | tercile_monotone | diff_over_rest_std | passes_separation_bar | promote_to_h6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rv_ratio | 0.0359 | 0.0359 | 0.3800 | 0.5000 | 0.0000 | 0.0000 | 0.2510 | 0.0000 | 0.0000 |
| range_ratio | 0.0808 | 0.0808 | 0.3800 | 0.5000 | 0.0000 | 1.0000 | 0.2281 | 0.0000 | 0.0000 |
| rvs_down_share | -0.1832 | 0.1832 | 0.3800 | 0.5000 | 0.0000 | 0.0000 | -0.3518 | 0.0000 | 0.0000 |
| hour_share_ratio | 0.2620 | 0.2620 | 0.3800 | 0.5000 | 0.0000 | 1.0000 | -0.3283 | 0.0000 | 0.0000 |
| venue_share_ratio | -0.1774 | 0.1774 | 0.3800 | 0.5000 | 0.0000 | 1.0000 | -0.0428 | 0.0000 | 0.0000 |
| hourly_autocorr | -0.0433 | 0.0433 | 0.3800 | 0.5000 | 0.0000 | 1.0000 | -0.0295 | 0.0000 | 0.0000 |
| night_minus_day | 0.1233 | 0.1233 | 0.3800 | 0.5000 | 0.0000 | 1.0000 | 0.2308 | 0.0000 | 0.0000 |

No state cleared the pre-declared bar.

## Worst months and the state they started in

| index | ret | btc | excess | rv_ratio | range_ratio | rvs_down_share | hour_share_ratio | venue_share_ratio | hourly_autocorr | night_minus_day | gate_open_before | breadth_before | disp_ratio_before | mkt_vol_before | gross_before | own63_before |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-04-30 00:00:00 | -0.1929 | 0.0278 | -0.2206 | 0.5975 | 0.8103 | 0.4713 | 0.9943 | 0.8606 | -0.0178 | 0.0288 | 1.0000 | 0.6000 | 0.8425 | 0.7466 | 0.4918 | -0.0579 |
| 2024-04-30 00:00:00 | -0.1896 | -0.1500 | -0.0396 | 1.4594 | 1.1688 | 0.4440 | 0.9491 | 1.2266 | -0.0123 | -0.0297 | 1.0000 | 0.8000 | 0.8928 | 0.6122 | 0.4422 | 0.4609 |
| 2022-11-30 00:00:00 | -0.1288 | -0.1623 | 0.0335 | 1.2775 | 0.9909 | 0.4181 | 1.0492 | 1.2186 | -0.0351 | -0.0216 | 0.0000 | 0.8500 | 1.6549 | 0.5474 | 0.0000 | 0.0000 |
| 2023-07-31 00:00:00 | -0.1139 | -0.0409 | -0.0729 | 1.7326 | 1.1818 | 0.5447 | 1.0148 | 0.8165 | 0.0113 | 0.0433 | 1.0000 | 0.6000 | 2.8412 | 0.5709 | 0.2024 | 0.2816 |
| 2024-01-31 00:00:00 | -0.1063 | 0.0075 | -0.1138 | 2.8883 | 1.5902 | 0.5438 | 0.8182 | 1.1931 | -0.0444 | -0.0193 | 1.0000 | 0.9000 | 1.6905 | 0.5456 | 0.3892 | 1.3066 |
| 2022-04-30 00:00:00 | -0.1049 | -0.1718 | 0.0669 |  |  | 0.4961 |  |  | 0.0019 | 0.1147 | 1.0000 | 1.0000 |  | 0.7740 | 0.7961 | 0.0341 |
| 2025-02-28 00:00:00 | -0.0966 | -0.1761 | 0.0795 | 1.0073 | 1.0591 | 0.5204 | 1.1337 | 1.0192 | -0.0291 | 0.0505 | 1.0000 | 0.4500 | 0.6255 | 0.8686 | 0.3246 | -0.0503 |
| 2023-08-31 00:00:00 | -0.0893 | -0.1129 | 0.0235 | 0.4450 | 0.7047 | 0.4670 | 0.9798 | 0.7014 | 0.0187 | -0.0334 | 1.0000 | 0.7000 | 1.0736 | 0.5786 | 0.3727 | 0.1807 |
| 2024-06-30 00:00:00 | -0.0878 | -0.0713 | -0.0165 | 0.5763 | 0.7603 | 0.5395 | 0.9190 | 0.9362 | -0.0362 | -0.0530 | 1.0000 | 0.6500 | 0.8454 | 0.7388 | 0.5317 | -0.0450 |
| 2024-08-31 00:00:00 | -0.0877 | -0.0874 | -0.0003 | 0.6016 | 0.8375 | 0.5350 | 1.0640 | 0.7078 | -0.0036 | 0.1126 | 1.0000 | 0.3500 | 0.5928 | 0.6072 | 0.9985 | -0.1219 |
| 2023-03-31 00:00:00 | -0.0707 | 0.2303 | -0.3011 | 0.6146 | 0.7831 | 0.5631 | 0.9461 | 1.7909 | -0.0236 | 0.0336 | 1.0000 | 0.4000 | 0.4767 | 0.6927 | 0.8500 | 0.3816 |
| 2024-07-31 00:00:00 | -0.0604 | 0.0310 | -0.0914 | 0.6426 | 0.8383 | 0.4209 | 1.0101 | 0.8031 | -0.0178 | -0.0581 | 0.0000 | 0.1000 | 0.3779 | 0.5533 | 0.0000 | 0.0351 |

## Reading

Any separation here is in-sample. A state that clears the bar would still have to be
pre-registered as H6 with its own kill criterion and confirmed out of sample before it
could change a rule; a state that fails is a rejected hypothesis.
