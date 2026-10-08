# Do volume / turnover states mark PR2026-10-H5's bad months?

Hypothesis generation only: no rule was changed, no trial was registered.
Months: 57; crash months (return <= -8%): 10.

The states are read at the last close before each month and compared with that
month's net 20 bps return and with that month's BTC return. Section 00.14 found the
failure mode is *market up, strategy down*, so the decisive column is `excess`
(strategy minus BTC).

## Pre-declared bar

`|Spearman(state, excess)| >= 0.25`, monotone terciles, and `|diff_over_rest_std| >= 0.50`.

## Crash versus rest

`welch_t` is the difference in means over the standard error of that difference;
it is reported for scale, and with nine candidates it is not a significance test.

| index | crash_mean | rest_mean | difference | rest_std | diff_over_rest_std | welch_t | crash_months |
| --- | --- | --- | --- | --- | --- | --- | --- |
| turnover | 0.0398 | 0.0391 | 0.0007 | 0.0194 | 0.0360 | 0.0807 | 10.0000 |
| turnover_ratio | 0.9323 | 1.0265 | -0.0942 | 0.4299 | -0.2192 | -0.7216 | 9.0000 |
| volume_ratio | 1.1703 | 1.0411 | 0.1292 | 0.6031 | 0.2143 | 0.9766 | 9.0000 |
| turnover_disp_ratio | 1.5100 | 1.0274 | 0.4826 | 0.7102 | 0.6795 | 0.9046 | 9.0000 |
| amihud_ratio | 1.0073 | 1.1054 | -0.0982 | 0.6619 | -0.1483 | -0.3981 | 9.0000 |
| mcap_hhi | 0.4118 | 0.4479 | -0.0360 | 0.0683 | -0.5277 | -2.1067 | 10.0000 |
| btc_share | 0.5990 | 0.6350 | -0.0360 | 0.0699 | -0.5150 | -1.9771 | 10.0000 |
| volume_top3_share | 0.8133 | 0.8334 | -0.0201 | 0.0474 | -0.4237 | -1.0258 | 10.0000 |
| holdings_turnover_ratio | 2.9973 | 1.1906 | 1.8067 | 0.8638 | 2.0915 | 1.1297 | 7.0000 |

## The states H5 already carries, Section 00.14's convention, full sample

Section 00.14 reported this table on 53 of the 57 months: it dropped every row with a
missing state, and two warm-ups bind early on - `disp_ratio` needs 126 usable
dispersion readings and `own63` needs 63 days of the return series. That discarded
2022-01..04, including 2022-04, a 10th crash month. The numbers below keep the same within-month
averaging convention but drop missing values state by state across all 57 months, so
they supersede the earlier table.

| index | crash_mean | rest_mean | difference | rest_std | diff_over_rest_std | welch_t | crash_months |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gate_open_mean | 0.6281 | 0.4730 | 0.1551 | 0.4346 | 0.3569 | 1.2074 | 10.0000 |
| breadth_mean | 0.3770 | 0.4670 | -0.0900 | 0.2914 | -0.3088 | -1.0825 | 10.0000 |
| disp_ratio_mean | 0.7506 | 0.9426 | -0.1920 | 0.5109 | -0.3757 | -1.2475 | 9.0000 |
| mkt_vol_mean | 0.7227 | 0.7130 | 0.0097 | 0.2084 | 0.0466 | 0.1575 | 10.0000 |
| gross_mean | 0.3069 | 0.2533 | 0.0536 | 0.2468 | 0.2173 | 0.6486 | 10.0000 |

## The same states read before the month instead (what an overlay could act on)

This is the convention the flow states above use, and it is the one an H6 overlay
would have to use. `own63_before` is identical in both tables.

| index | crash_mean | rest_mean | difference | rest_std | diff_over_rest_std | welch_t | crash_months |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gate_open_before | 0.9000 | 0.4468 | 0.4532 | 0.5025 | 0.9018 | 3.6551 | 10.0000 |
| breadth_before | 0.6900 | 0.3723 | 0.3177 | 0.3354 | 0.9472 | 3.9422 | 10.0000 |
| disp_ratio_before | 1.2288 | 0.9262 | 0.3026 | 0.7943 | 0.3810 | 1.1230 | 9.0000 |
| mkt_vol_before | 0.6590 | 0.7330 | -0.0740 | 0.2342 | -0.3161 | -1.4949 | 10.0000 |
| own63_before | 0.1989 | 0.1193 | 0.0796 | 0.2627 | 0.3028 | 0.5629 | 10.0000 |
| gross_before | 0.4549 | 0.2264 | 0.2285 | 0.3162 | 0.7225 | 2.2729 | 10.0000 |

## Rank information against next-month excess return

| index | observations | spearman | p_value |
| --- | --- | --- | --- |
| turnover | 57.0000 | -0.0686 | 0.6102 |
| turnover_ratio | 53.0000 | 0.0829 | 0.5525 |
| volume_ratio | 53.0000 | 0.0899 | 0.5191 |
| turnover_disp_ratio | 53.0000 | 0.1264 | 0.3630 |
| amihud_ratio | 53.0000 | -0.1090 | 0.4335 |
| mcap_hhi | 57.0000 | 0.1664 | 0.2108 |
| btc_share | 57.0000 | 0.1581 | 0.2351 |
| volume_top3_share | 57.0000 | -0.1705 | 0.1993 |
| holdings_turnover_ratio | 28.0000 | -0.1746 | 0.3659 |

## Excess return by state tercile (1 = lowest state, 3 = highest)

| index | state | bucket | months | mean_ret | mean_btc | mean_excess | hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | turnover | 1.0000 | 19.0000 | 0.0732 | 0.0202 | 0.0530 | 0.5263 |
| 1 | turnover | 2.0000 | 19.0000 | 0.1161 | 0.0758 | 0.0403 | 0.4737 |
| 2 | turnover | 3.0000 | 19.0000 | 0.0133 | -0.0279 | 0.0412 | 0.2105 |
| 3 | turnover_ratio | 1.0000 | 18.0000 | 0.0734 | 0.0409 | 0.0324 | 0.5000 |
| 4 | turnover_ratio | 2.0000 | 17.0000 | 0.0712 | 0.0376 | 0.0337 | 0.4118 |
| 5 | turnover_ratio | 3.0000 | 18.0000 | 0.0772 | 0.0046 | 0.0726 | 0.3333 |
| 6 | volume_ratio | 1.0000 | 18.0000 | 0.0687 | 0.0595 | 0.0092 | 0.3889 |
| 7 | volume_ratio | 2.0000 | 17.0000 | 0.0430 | 0.0093 | 0.0336 | 0.4118 |
| 8 | volume_ratio | 3.0000 | 18.0000 | 0.1085 | 0.0126 | 0.0958 | 0.4444 |
| 9 | turnover_disp_ratio | 1.0000 | 18.0000 | 0.0594 | 0.0574 | 0.0020 | 0.3889 |
| 10 | turnover_disp_ratio | 2.0000 | 17.0000 | 0.0974 | 0.0019 | 0.0956 | 0.5294 |
| 11 | turnover_disp_ratio | 3.0000 | 18.0000 | 0.0664 | 0.0217 | 0.0446 | 0.3333 |
| 12 | amihud_ratio | 1.0000 | 18.0000 | 0.0796 | 0.0210 | 0.0585 | 0.3889 |
| 13 | amihud_ratio | 2.0000 | 17.0000 | 0.0991 | 0.0282 | 0.0709 | 0.5882 |
| 14 | amihud_ratio | 3.0000 | 18.0000 | 0.0446 | 0.0333 | 0.0114 | 0.2778 |
| 15 | mcap_hhi | 1.0000 | 19.0000 | 0.0054 | -0.0127 | 0.0181 | 0.2105 |
| 16 | mcap_hhi | 2.0000 | 19.0000 | 0.0632 | 0.0500 | 0.0132 | 0.4737 |
| 17 | mcap_hhi | 3.0000 | 19.0000 | 0.1340 | 0.0307 | 0.1032 | 0.5263 |
| 18 | btc_share | 1.0000 | 19.0000 | 0.0054 | -0.0127 | 0.0181 | 0.2105 |
| 19 | btc_share | 2.0000 | 19.0000 | 0.0632 | 0.0500 | 0.0132 | 0.4737 |
| 20 | btc_share | 3.0000 | 19.0000 | 0.1340 | 0.0307 | 0.1032 | 0.5263 |
| 21 | volume_top3_share | 1.0000 | 19.0000 | 0.0189 | -0.0342 | 0.0530 | 0.3158 |
| 22 | volume_top3_share | 2.0000 | 19.0000 | 0.1168 | 0.0288 | 0.0880 | 0.5263 |
| 23 | volume_top3_share | 3.0000 | 19.0000 | 0.0669 | 0.0734 | -0.0065 | 0.3684 |
| 24 | holdings_turnover_ratio | 1.0000 | 10.0000 | 0.0683 | 0.0039 | 0.0643 | 0.5000 |
| 25 | holdings_turnover_ratio | 2.0000 | 9.0000 | 0.2013 | 0.1228 | 0.0785 | 0.7778 |
| 26 | holdings_turnover_ratio | 3.0000 | 9.0000 | 0.0663 | 0.0490 | 0.0172 | 0.5556 |

## Correlation with the states H5 already carries

A value near zero means the state carries information the frozen spec cannot see.

| index | gate_open_before | breadth_before | disp_ratio_before | mkt_vol_before | own63_before | gross_before |
| --- | --- | --- | --- | --- | --- | --- |
| turnover | -0.2798 | -0.1577 | 0.1197 | 0.2377 | -0.1880 | -0.2667 |
| turnover_ratio | -0.1908 | -0.1274 | 0.1631 | 0.0055 | 0.0409 | -0.2176 |
| volume_ratio | 0.2602 | 0.1208 | 0.2259 | -0.0353 | 0.2808 | 0.1197 |
| turnover_disp_ratio | 0.2329 | 0.2169 | 0.3413 | -0.3041 | 0.2784 | 0.1423 |
| amihud_ratio | -0.0842 | -0.1357 | -0.1484 | -0.0523 | -0.1800 | 0.0871 |
| mcap_hhi | 0.1709 | -0.0323 | -0.2470 | -0.2451 | 0.2331 | 0.1455 |
| btc_share | 0.1709 | -0.0364 | -0.2507 | -0.2278 | 0.2392 | 0.1400 |
| volume_top3_share | -0.1452 | -0.3023 | -0.4642 | -0.0465 | -0.2495 | -0.0584 |
| holdings_turnover_ratio | -0.1443 | 0.2059 | 0.3060 | -0.2868 | -0.1062 | -0.1081 |

## Verdicts

| index | spearman | abs_spearman | ic_bar | separation_bar | passes_ic_bar | tercile_monotone | diff_over_rest_std | passes_separation_bar | promote_to_h6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| turnover | -0.0686 | 0.0686 | 0.2500 | 0.5000 | 0.0000 | 0.0000 | 0.0360 | 0.0000 | 0.0000 |
| turnover_ratio | 0.0829 | 0.0829 | 0.2500 | 0.5000 | 0.0000 | 1.0000 | -0.2192 | 0.0000 | 0.0000 |
| volume_ratio | 0.0899 | 0.0899 | 0.2500 | 0.5000 | 0.0000 | 1.0000 | 0.2143 | 0.0000 | 0.0000 |
| turnover_disp_ratio | 0.1264 | 0.1264 | 0.2500 | 0.5000 | 0.0000 | 0.0000 | 0.6795 | 1.0000 | 0.0000 |
| amihud_ratio | -0.1090 | 0.1090 | 0.2500 | 0.5000 | 0.0000 | 0.0000 | -0.1483 | 0.0000 | 0.0000 |
| mcap_hhi | 0.1664 | 0.1664 | 0.2500 | 0.5000 | 0.0000 | 0.0000 | -0.5277 | 1.0000 | 0.0000 |
| btc_share | 0.1581 | 0.1581 | 0.2500 | 0.5000 | 0.0000 | 0.0000 | -0.5150 | 1.0000 | 0.0000 |
| volume_top3_share | -0.1705 | 0.1705 | 0.2500 | 0.5000 | 0.0000 | 0.0000 | -0.4237 | 0.0000 | 0.0000 |
| holdings_turnover_ratio | -0.1746 | 0.1746 | 0.2500 | 0.5000 | 0.0000 | 0.0000 | 2.0915 | 1.0000 | 0.0000 |

No state cleared the pre-declared bar.

## Worst months and the state they started in

| index | ret | btc | excess | turnover | turnover_ratio | volume_ratio | turnover_disp_ratio | amihud_ratio | mcap_hhi | btc_share | volume_top3_share | holdings_turnover_ratio | gate_open_before | gate_open_mean | breadth_before | breadth_mean | disp_ratio_before | disp_ratio_mean | mkt_vol_before | mkt_vol_mean | gross_before | gross_mean | own63_before |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-04-30 00:00:00 | -0.1929 | 0.0278 | -0.2206 | 0.0364 | 0.5941 | 0.7428 | 0.5109 | 1.8205 | 0.3979 | 0.5826 | 0.8741 |  | 1.0000 | 1.0000 | 0.6000 | 0.6500 | 0.8425 | 0.5927 | 0.7466 | 1.0756 | 0.4918 | 0.9007 | -0.0579 |
| 2024-04-30 00:00:00 | -0.1896 | -0.1500 | -0.0396 | 0.0188 | 0.6433 | 1.2328 | 0.9521 | 0.9681 | 0.4297 | 0.6227 | 0.7801 | 0.9479 | 1.0000 | 1.0000 | 0.8000 | 0.3133 | 0.8928 | 0.6878 | 0.6122 | 0.7727 | 0.4422 | 0.3427 | 0.4609 |
| 2022-11-30 00:00:00 | -0.1288 | -0.1623 | 0.0335 | 0.1057 | 1.6342 | 1.3206 | 0.7431 | 0.3910 | 0.3328 | 0.5125 | 0.8728 |  | 0.0000 | 0.1000 | 0.8500 | 0.3150 | 1.6549 | 1.1292 | 0.5474 | 0.8108 | 0.0000 | 0.0343 | 0.0000 |
| 2023-07-31 00:00:00 | -0.1139 | -0.0409 | -0.0729 | 0.0546 | 1.2795 | 1.5747 | 5.3459 | 1.6534 | 0.4288 | 0.6075 | 0.8029 | 11.9061 | 1.0000 | 1.0000 | 0.6000 | 0.8032 | 2.8412 | 1.6640 | 0.5709 | 0.5714 | 0.2024 | 0.3400 | 0.2816 |
| 2024-01-31 00:00:00 | -0.1063 | 0.0075 | -0.1138 | 0.0232 | 0.8687 | 1.2091 | 1.4168 | 0.6040 | 0.4209 | 0.6132 | 0.7974 | 1.6799 | 1.0000 | 1.0000 | 0.9000 | 0.4935 | 1.6905 | 0.7036 | 0.5456 | 0.6014 | 0.3892 | 0.4054 | 1.3066 |
| 2022-04-30 00:00:00 | -0.1049 | -0.1718 | 0.0669 | 0.0505 |  |  |  |  | 0.3413 | 0.5278 | 0.6795 |  | 1.0000 | 0.4333 | 1.0000 | 0.4417 |  |  | 0.7740 | 0.7689 | 0.7961 | 0.2781 | 0.0341 |
| 2025-02-28 00:00:00 | -0.0966 | -0.1761 | 0.0795 | 0.0312 | 0.9680 | 1.4643 | 0.6513 | 0.2757 | 0.4665 | 0.6658 | 0.8465 | 0.2615 | 1.0000 | 0.5714 | 0.4500 | 0.0714 | 0.6255 | 0.5265 | 0.8686 | 0.8249 | 0.3246 | 0.2092 | -0.0503 |
| 2023-08-31 00:00:00 | -0.0893 | -0.1129 | 0.0235 | 0.0230 | 0.6252 | 0.7236 | 0.6563 | 1.2685 | 0.4099 | 0.5933 | 0.7967 | 0.7428 | 1.0000 | 0.5484 | 0.7000 | 0.2000 | 1.0736 | 0.5242 | 0.5786 | 0.4717 | 0.3727 | 0.2283 | 0.1807 |
| 2024-06-30 00:00:00 | -0.0878 | -0.0713 | -0.0165 | 0.0258 | 0.8163 | 1.1654 | 2.5326 | 0.1955 | 0.4404 | 0.6258 | 0.8239 | 4.7105 | 1.0000 | 0.4667 | 0.6500 | 0.3300 | 0.8454 | 0.5016 | 0.7388 | 0.6207 | 0.5317 | 0.2047 | -0.0450 |
| 2024-08-31 00:00:00 | -0.0877 | -0.0874 | -0.0003 | 0.0294 | 0.9618 | 1.0998 | 0.7813 | 1.8887 | 0.4502 | 0.6390 | 0.8591 | 0.7322 | 1.0000 | 0.1613 | 0.3500 | 0.1516 | 0.5928 | 0.4256 | 0.6072 | 0.7089 | 0.9985 | 0.1257 | -0.1219 |
| 2023-03-31 00:00:00 | -0.0707 | 0.2303 | -0.3011 | 0.0392 | 0.6039 | 0.6627 | 0.4096 | 1.4769 | 0.3698 | 0.5528 | 0.8789 |  | 1.0000 | 1.0000 | 0.4000 | 0.2726 | 0.4767 | 0.5039 | 0.6927 | 0.7523 | 0.8500 | 0.5226 | 0.3816 |
| 2024-07-31 00:00:00 | -0.0604 | 0.0310 | -0.0914 | 0.0166 | 0.5273 | 0.6334 | 0.7476 | 2.3546 | 0.4481 | 0.6324 | 0.8390 | 1.1222 | 0.0000 | 0.4516 | 0.1000 | 0.3500 | 0.3779 | 0.4415 | 0.5533 | 0.6100 | 0.0000 | 0.3385 | 0.0351 |

## Reading

Any separation here is in-sample. A state that clears the bar would still have to be
pre-registered as H6 with its own kill criterion and confirmed out of sample before it
could change a rule; a state that fails is recorded as a rejected hypothesis.
