# Do perpetual funding-rate states mark PR2026-10-H5's bad months?

Hypothesis generation only: no rule was changed, no trial was registered.
Months: 57; crash months (return <= -8%): 10.

Funding is the only derivatives-positioning information the project holds; it cannot
be built from the spot price, volume and market-cap panel. States are read at the last
close before each month and compared with that month's net 20 bps return and its BTC
return, because the failure mode is market up and strategy down.

## Pre-declared bar (family-wise over all three screens)

`|Spearman(state, excess)| >= 0.38` - the 5% two-sided level divided by the
twenty candidate states of Sections 00.15, 00.16 and this one - plus monotone terciles
and `|diff_over_rest_std| >= 0.50`.

## Point-in-time Top20 coverage of the funding feed

| index | metric | value |
| --- | --- | --- |
| 0 | coins with funding history | 52.0000 |
| 1 | distinct point-in-time members | 53.0000 |
| 2 | members without funding history | 5.0000 |
| 3 | member-days with funding | 33,043.0000 |
| 4 | member-days total | 34,500.0000 |
| 5 | member-day coverage | 0.9578 |
| 6 | days below the five-member floor | 0.0000 |

## Crash versus rest

| index | crash_mean | rest_mean | difference | rest_std | diff_over_rest_std | welch_t | crash_months |
| --- | --- | --- | --- | --- | --- | --- | --- |
| funding_level | 3.1945 | 0.6998 | 2.4947 | 2.2290 | 1.1192 | 1.9896 | 10.0000 |
| funding_pct | 0.6273 | 0.4764 | 0.1509 | 0.2983 | 0.5057 | 1.5243 | 9.0000 |
| funding_positive_share | 0.8428 | 0.6952 | 0.1476 | 0.1938 | 0.7614 | 3.5679 | 10.0000 |
| funding_disp_ratio | 1.0465 | 1.1112 | -0.0646 | 0.5203 | -0.1243 | -0.2710 | 9.0000 |

## Rank information against next-month excess return

| index | observations | spearman | p_value |
| --- | --- | --- | --- |
| funding_level | 57.0000 | 0.1624 | 0.2223 |
| funding_pct | 53.0000 | 0.0882 | 0.5271 |
| funding_positive_share | 57.0000 | 0.1676 | 0.2073 |
| funding_disp_ratio | 53.0000 | 0.0668 | 0.6323 |

## Excess return by state tercile (1 = lowest state, 3 = highest)

| index | state | bucket | months | mean_ret | mean_btc | mean_excess | hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | funding_level | 1.0000 | 19.0000 | 0.0313 | 0.0151 | 0.0161 | 0.2105 |
| 1 | funding_level | 2.0000 | 19.0000 | 0.0439 | -0.0115 | 0.0553 | 0.4737 |
| 2 | funding_level | 3.0000 | 19.0000 | 0.1274 | 0.0644 | 0.0631 | 0.5263 |
| 3 | funding_pct | 1.0000 | 18.0000 | 0.0176 | -0.0181 | 0.0357 | 0.2222 |
| 4 | funding_pct | 2.0000 | 17.0000 | 0.0798 | 0.0473 | 0.0325 | 0.3529 |
| 5 | funding_pct | 3.0000 | 18.0000 | 0.1248 | 0.0544 | 0.0704 | 0.6667 |
| 6 | funding_positive_share | 1.0000 | 19.0000 | 0.0395 | 0.0270 | 0.0124 | 0.2632 |
| 7 | funding_positive_share | 2.0000 | 19.0000 | 0.0751 | -0.0065 | 0.0816 | 0.4211 |
| 8 | funding_positive_share | 3.0000 | 19.0000 | 0.0881 | 0.0475 | 0.0405 | 0.5263 |
| 9 | funding_disp_ratio | 1.0000 | 18.0000 | 0.0609 | 0.0513 | 0.0096 | 0.5000 |
| 10 | funding_disp_ratio | 2.0000 | 17.0000 | 0.1167 | 0.0225 | 0.0942 | 0.4706 |
| 11 | funding_disp_ratio | 3.0000 | 18.0000 | 0.0466 | 0.0084 | 0.0382 | 0.2778 |

## Correlation with the states H5 already carries

| index | gate_open_before | breadth_before | disp_ratio_before | mkt_vol_before | own63_before | gross_before |
| --- | --- | --- | --- | --- | --- | --- |
| funding_level | 0.6471 | 0.6586 | 0.2092 | -0.3971 | 0.4931 | 0.6132 |
| funding_pct | 0.5551 | 0.7656 | 0.3463 | -0.4380 | 0.4816 | 0.5129 |
| funding_positive_share | 0.6984 | 0.6609 | 0.2311 | -0.3508 | 0.5187 | 0.6517 |
| funding_disp_ratio | -0.2181 | -0.2573 | 0.1423 | 0.2631 | -0.2494 | -0.2473 |

## Verdicts

| index | spearman | abs_spearman | ic_bar | separation_bar | passes_ic_bar | tercile_monotone | diff_over_rest_std | passes_separation_bar | promote_to_h6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| funding_level | 0.1624 | 0.1624 | 0.3800 | 0.5000 | 0.0000 | 1.0000 | 1.1192 | 1.0000 | 0.0000 |
| funding_pct | 0.0882 | 0.0882 | 0.3800 | 0.5000 | 0.0000 | 0.0000 | 0.5057 | 1.0000 | 0.0000 |
| funding_positive_share | 0.1676 | 0.1676 | 0.3800 | 0.5000 | 0.0000 | 0.0000 | 0.7614 | 1.0000 | 0.0000 |
| funding_disp_ratio | 0.0668 | 0.0668 | 0.3800 | 0.5000 | 0.0000 | 0.0000 | -0.1243 | 0.0000 | 0.0000 |

No state cleared the pre-declared bar.

## Worst months and the state they started in

| index | ret | btc | excess | funding_level | funding_pct | funding_positive_share | funding_disp_ratio | gate_open_before | breadth_before | disp_ratio_before | mkt_vol_before | gross_before | own63_before |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-04-30 00:00:00 | -0.1929 | 0.0278 | -0.2206 | 0.5179 | 0.6175 | 0.7427 | 0.8570 | 1.0000 | 0.6000 | 0.8425 | 0.7466 | 0.4918 | -0.0579 |
| 2024-04-30 00:00:00 | -0.1896 | -0.1500 | -0.0396 | 10.9552 | 0.9323 | 0.9857 | 1.2007 | 1.0000 | 0.8000 | 0.8928 | 0.6122 | 0.4422 | 0.4609 |
| 2022-11-30 00:00:00 | -0.1288 | -0.1623 | 0.0335 | 1.0719 | 0.8645 | 0.7293 | 0.4879 | 0.0000 | 0.8500 | 1.6549 | 0.5474 | 0.0000 | 0.0000 |
| 2023-07-31 00:00:00 | -0.1139 | -0.0409 | -0.0729 | 0.1509 | 0.3984 | 0.7286 | 1.6449 | 1.0000 | 0.6000 | 2.8412 | 0.5709 | 0.2024 | 0.2816 |
| 2024-01-31 00:00:00 | -0.1063 | 0.0075 | -0.1138 | 9.5650 | 0.9960 | 0.9500 | 2.5726 | 1.0000 | 0.9000 | 1.6905 | 0.5456 | 0.3892 | 1.3066 |
| 2022-04-30 00:00:00 | -0.1049 | -0.1718 | 0.0669 | 2.3688 |  | 0.8880 |  | 1.0000 | 1.0000 |  | 0.7740 | 0.7961 | 0.0341 |
| 2025-02-28 00:00:00 | -0.0966 | -0.1761 | 0.0795 | 1.5595 | 0.4542 | 0.8033 | 0.7136 | 1.0000 | 0.4500 | 0.6255 | 0.8686 | 0.3246 | -0.0503 |
| 2023-08-31 00:00:00 | -0.0893 | -0.1129 | 0.0235 | 1.3791 | 0.6574 | 0.8429 | 0.6240 | 1.0000 | 0.7000 | 1.0736 | 0.5786 | 0.3727 | 0.1807 |
| 2024-06-30 00:00:00 | -0.0878 | -0.0713 | -0.0165 | 3.0727 | 0.5219 | 0.9421 | 0.6052 | 1.0000 | 0.6500 | 0.8454 | 0.7388 | 0.5317 | -0.0450 |
| 2024-08-31 00:00:00 | -0.0877 | -0.0874 | -0.0003 | 1.3036 | 0.2032 | 0.8154 | 0.7131 | 1.0000 | 0.3500 | 0.5928 | 0.6072 | 0.9985 | -0.1219 |
| 2023-03-31 00:00:00 | -0.0707 | 0.2303 | -0.3011 | 2.0446 | 0.8606 | 0.8822 | 0.4154 | 1.0000 | 0.4000 | 0.4767 | 0.6927 | 0.8500 | 0.3816 |
| 2024-07-31 00:00:00 | -0.0604 | 0.0310 | -0.0914 | 2.0433 | 0.2510 | 0.8598 | 0.6854 | 0.0000 | 0.1000 | 0.3779 | 0.5533 | 0.0000 | 0.0351 |

## Reading

Any separation here is in-sample. A state that clears the bar would still have to be
pre-registered as H6 with its own kill criterion and confirmed out of sample before it
could change a rule. Deployment note: Binance publishes funding archives monthly rather
than daily and fapi.binance.com is unreachable from this network, so even a promoted
state could be backtested here but not driven live without another data route.
