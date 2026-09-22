# Decision-Point Ablation — Stop, BTC Gate, and Re-entry

This audit changes one inherited decision at a time while keeping the
point-in-time Top20 universe and CTREND-breakout top-1 selection fixed.
Every variant is evaluated across all 21 rebalance phases and as a
fully staggered 21-tranche basket. The basket is the phase-invariant
benchmark; the phase median and minimum are the robustness statistics.

## External evidence used to choose what to test

- Han, Kang, Ryu: cross-sectional crypto momentum weakens after realistic
  costs and holding-period fluctuations; time-series evidence is stronger.
  <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>
- Kaminski and Lo: stop-loss policies can improve return and reduce
  volatility at longer sampling frequencies, but the result is regime dependent.
  <https://doi.org/10.1016/j.finmar.2013.07.001>
- Sadaqat and Butt: stop-loss momentum outperformed ordinary momentum
  across 147 cryptocurrencies from 2015-01 through 2022-06.
  <https://doi.org/10.1016/j.jbef.2023.100833>
- Le and Ruthbah: crypto trend following is sensitive to moving-average
  horizon and transaction costs; BTC performed best around 65 days, while
  ETH and a large-cap non-BTC index performed better around 20 days.
  <https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf>
- Duarte: trailing stops with explicit re-entry thresholds produced mixed
  results, but reduced losses in highly volatile markets.
  <https://doi.org/10.24018/ejbmr.2022.7.3.1426>

## Audit conclusion

- The inherited 11-day/two-day BTC gate is a local parameter spike.
  The 21-tranche basket returns 5.51x at 11 days, but 3.05x at 10 days
  and 1.98x at 14 days; one-day and five-day confirmation return 2.20x
  and 2.30x. It must not be treated as a validated production rule.
- Immediate re-entry is rejected in this sample. Requiring the next
  scheduled rebalance returns 5.51x, versus 1.49x when both the own stop
  and BTC gate re-enter immediately.
- The 75-day/three-day own stop sits inside a broad 50-100 day and
  1-3 confirmation plateau. It is acceptable as a research setting but is
  not uniquely optimal.
- No variant in this audit is production-ready until the BTC gate is
  replaced or independently validated.

## Core ablations at 20bps

| index | family | variant_id | cost_bps | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_turnover | phase_median_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | core | full_current | 20.0000 | 3.9363 | 0.6120 | 22.4353 | 0.7798 | -0.7630 | 16.9275 | 0.2562 |
| 3 | core | btc_gate_only | 20.0000 | 3.6470 | 0.6005 | 18.5674 | 0.7530 | -0.7956 | 18.1971 | 0.2725 |
| 9 | core | no_overlay | 20.0000 | 1.6428 | 0.1140 | 8.1146 | 0.5605 | -0.9730 | 29.8348 | 0.9936 |
| 11 | core | own_stop_immediate_reentry | 20.0000 | 1.5701 | 0.0885 | 5.4176 | 0.5386 | -0.9615 | 32.3739 | 0.8591 |
| 13 | core | own_stop_only | 20.0000 | 1.3940 | 0.0888 | 8.1199 | 0.5107 | -0.9652 | 27.7188 | 0.8052 |
| 7 | core | full_immediate_reentry | 20.0000 | 1.1192 | 0.1425 | 4.7129 | 0.3555 | -0.9151 | 39.5681 | 0.4835 |
| 1 | core | btc_gate_immediate_reentry | 20.0000 | 0.9083 | 0.1571 | 4.5360 | 0.2928 | -0.9186 | 41.6841 | 0.5223 |

## BTC gate variants at 20bps

| index | family | variant_id | cost_bps | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_turnover | phase_median_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | gate | gate_trailing11 | 20.0000 | 3.9363 | 0.6120 | 22.4353 | 0.7798 | -0.7630 | 16.9275 | 0.2562 |
| 17 | gate | gate_ma20 | 20.0000 | 2.1363 | 0.1421 | 5.8672 | 0.5422 | -0.8841 | 17.1391 | 0.2730 |
| 21 | gate | gate_ma50 | 20.0000 | 2.0440 | 0.1140 | 29.0052 | 0.5441 | -0.9245 | 16.7159 | 0.3606 |
| 23 | gate | gate_ma65 | 20.0000 | 1.5474 | 0.1059 | 12.7090 | 0.4571 | -0.9298 | 16.2928 | 0.3751 |
| 15 | gate | gate_ma100 | 20.0000 | 1.3954 | 0.1730 | 13.9824 | 0.4255 | -0.9244 | 15.8696 | 0.3948 |
| 19 | gate | gate_ma200 | 20.0000 | 1.3028 | 0.1027 | 11.4369 | 0.4123 | -0.9433 | 15.8696 | 0.4203 |

## Own-stop grid at 20bps

| index | family | variant_id | cost_bps | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_turnover | phase_median_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 63 | stop_grid | stop_ma75_c1 | 20.0000 | 3.9660 | 0.6098 | 21.8419 | 0.7629 | -0.7605 | 16.7159 | 0.2522 |
| 65 | stop_grid | stop_ma75_c2 | 20.0000 | 3.9409 | 0.6118 | 22.2028 | 0.7604 | -0.7714 | 16.7159 | 0.2551 |
| 59 | stop_grid | stop_ma65_c2 | 20.0000 | 3.9409 | 0.6118 | 22.0259 | 0.7604 | -0.7706 | 16.9275 | 0.2551 |
| 67 | stop_grid | stop_ma75_c3 | 20.0000 | 3.9363 | 0.6120 | 22.4353 | 0.7798 | -0.7630 | 16.9275 | 0.2562 |
| 61 | stop_grid | stop_ma65_c3 | 20.0000 | 3.9363 | 0.6120 | 21.9577 | 0.7943 | -0.7664 | 16.9275 | 0.2562 |
| 29 | stop_grid | stop_ma100_c2 | 20.0000 | 3.8050 | 0.4345 | 17.3087 | 0.7457 | -0.7529 | 16.5043 | 0.2475 |
| 31 | stop_grid | stop_ma100_c3 | 20.0000 | 3.8050 | 0.4346 | 17.8928 | 0.7881 | -0.7529 | 16.5043 | 0.2481 |
| 27 | stop_grid | stop_ma100_c1 | 20.0000 | 3.7918 | 0.4527 | 17.5597 | 0.7492 | -0.7529 | 16.5043 | 0.2452 |
| 39 | stop_grid | stop_ma200_c1 | 20.0000 | 3.7382 | 0.5391 | 11.8727 | 0.7550 | -0.7839 | 15.2348 | 0.2267 |
| 53 | stop_grid | stop_ma50_c2 | 20.0000 | 3.6874 | 0.6005 | 21.4632 | 0.7631 | -0.7529 | 17.1391 | 0.2649 |
| 51 | stop_grid | stop_ma50_c1 | 20.0000 | 3.6669 | 0.6125 | 21.8203 | 0.7341 | -0.7554 | 17.1391 | 0.2609 |
| 57 | stop_grid | stop_ma65_c1 | 20.0000 | 3.6638 | 0.6098 | 21.8419 | 0.7552 | -0.7644 | 16.9275 | 0.2522 |
| 41 | stop_grid | stop_ma200_c2 | 20.0000 | 3.5872 | 0.4970 | 11.5462 | 0.7453 | -0.8200 | 15.2348 | 0.2296 |
| 55 | stop_grid | stop_ma50_c3 | 20.0000 | 3.5484 | 0.6005 | 18.5674 | 0.7563 | -0.7600 | 17.3507 | 0.2649 |
| 47 | stop_grid | stop_ma20_c2 | 20.0000 | 3.3613 | 0.4070 | 13.0164 | 0.6857 | -0.7538 | 17.7739 | 0.2348 |
| 43 | stop_grid | stop_ma200_c3 | 20.0000 | 3.3148 | 0.4932 | 10.5614 | 0.7453 | -0.8226 | 15.2348 | 0.2313 |
| 45 | stop_grid | stop_ma20_c1 | 20.0000 | 3.1345 | 0.4053 | 8.1953 | 0.6964 | -0.7548 | 17.3507 | 0.2180 |
| 49 | stop_grid | stop_ma20_c3 | 20.0000 | 3.0232 | 0.4110 | 19.7964 | 0.6750 | -0.7529 | 17.7739 | 0.2470 |
| 33 | stop_grid | stop_ma150_c1 | 20.0000 | 2.9273 | 0.4070 | 11.8784 | 0.6549 | -0.7558 | 15.6580 | 0.2232 |
| 37 | stop_grid | stop_ma150_c3 | 20.0000 | 2.8177 | 0.4880 | 18.8503 | 0.6427 | -0.7778 | 15.6580 | 0.2325 |
| 35 | stop_grid | stop_ma150_c2 | 20.0000 | 2.7185 | 0.5039 | 18.8596 | 0.6410 | -0.7634 | 15.6580 | 0.2301 |

## BTC trailing-lookback grid at 20bps

| index | family | variant_id | cost_bps | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_turnover | phase_median_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 81 | trailing_grid | trailing_lb11_c2 | 20.0000 | 3.9363 | 0.6120 | 22.4353 | 0.7798 | -0.7630 | 16.9275 | 0.2562 |
| 89 | trailing_grid | trailing_lb30_c2 | 20.0000 | 2.9614 | 0.2566 | 29.9231 | 0.6522 | -0.8583 | 17.1391 | 0.3507 |
| 91 | trailing_grid | trailing_lb50_c2 | 20.0000 | 2.9087 | 0.3625 | 25.1950 | 0.6628 | -0.8136 | 16.7159 | 0.3855 |
| 79 | trailing_grid | trailing_lb10_c2 | 20.0000 | 2.4478 | 0.4895 | 8.0432 | 0.6087 | -0.7706 | 17.3507 | 0.2452 |
| 77 | trailing_grid | trailing_lb100_c2 | 20.0000 | 2.1050 | 0.1350 | 8.4137 | 0.5483 | -0.9328 | 15.0232 | 0.3710 |
| 87 | trailing_grid | trailing_lb20_c2 | 20.0000 | 1.9347 | 0.2925 | 12.1119 | 0.5154 | -0.8586 | 16.9275 | 0.3049 |
| 97 | trailing_grid | trailing_lb7_c2 | 20.0000 | 1.8470 | 0.3674 | 5.9189 | 0.5108 | -0.6859 | 16.9275 | 0.1913 |
| 95 | trailing_grid | trailing_lb65_c2 | 20.0000 | 1.4870 | 0.2968 | 19.7671 | 0.4423 | -0.8838 | 15.4464 | 0.3843 |
| 83 | trailing_grid | trailing_lb14_c2 | 20.0000 | 1.4222 | 0.2411 | 7.7354 | 0.4059 | -0.8716 | 17.3507 | 0.2829 |
| 85 | trailing_grid | trailing_lb200_c2 | 20.0000 | 1.2711 | 0.1617 | 4.2304 | 0.3920 | -0.9274 | 17.9855 | 0.4777 |
| 93 | trailing_grid | trailing_lb5_c2 | 20.0000 | 1.0775 | 0.3011 | 10.1916 | 0.2505 | -0.7407 | 16.9275 | 0.1559 |

## BTC 11-day gate confirmation grid at 20bps

| index | family | variant_id | cost_bps | phase_median_multiple | phase_min_multiple | phase_max_multiple | phase_median_sharpe | phase_worst_drawdown | phase_median_turnover | phase_median_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 71 | trailing_confirm | trailing_lb11_c2 | 20.0000 | 3.9363 | 0.6120 | 22.4353 | 0.7798 | -0.7630 | 16.9275 | 0.2562 |
| 73 | trailing_confirm | trailing_lb11_c3 | 20.0000 | 3.8154 | 0.9066 | 20.3055 | 0.7214 | -0.6804 | 17.3507 | 0.2916 |
| 69 | trailing_confirm | trailing_lb11_c1 | 20.0000 | 1.8694 | 0.3643 | 7.5650 | 0.5032 | -0.7878 | 17.3507 | 0.1896 |
| 75 | trailing_confirm | trailing_lb11_c5 | 20.0000 | 1.3146 | 0.1785 | 18.9683 | 0.3901 | -0.8685 | 16.9275 | 0.3072 |

## Fully staggered 21-tranche results

| index | family | variant_id | cost_bps | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | core | btc_gate_immediate_reentry | 2.0000 | 1.9551 | 0.1525 | 0.5301 | -0.5565 |
| 4 | core | btc_gate_only | 2.0000 | 6.0123 | 0.4620 | 1.1502 | -0.3377 |
| 6 | core | full_current | 2.0000 | 6.3719 | 0.4801 | 1.1891 | -0.3269 |
| 12 | core | full_immediate_reentry | 2.0000 | 2.0888 | 0.1688 | 0.5580 | -0.5464 |
| 0 | core | no_overlay | 2.0000 | 3.1157 | 0.2720 | 0.6918 | -0.6680 |
| 8 | core | own_stop_immediate_reentry | 2.0000 | 2.9164 | 0.2543 | 0.6702 | -0.6176 |
| 2 | core | own_stop_only | 2.0000 | 2.9961 | 0.2615 | 0.6789 | -0.5608 |
| 22 | gate | gate_ma100 | 2.0000 | 2.7835 | 0.2420 | 0.6988 | -0.5024 |
| 16 | gate | gate_ma20 | 2.0000 | 2.3978 | 0.2034 | 0.6719 | -0.4201 |
| 24 | gate | gate_ma200 | 2.0000 | 2.3606 | 0.1994 | 0.6161 | -0.5477 |
| 18 | gate | gate_ma50 | 2.0000 | 3.3352 | 0.2905 | 0.7835 | -0.5250 |
| 20 | gate | gate_ma65 | 2.0000 | 2.3495 | 0.1982 | 0.6181 | -0.5729 |
| 14 | gate | gate_trailing11 | 2.0000 | 6.3719 | 0.4801 | 1.1891 | -0.3269 |
| 50 | stop_grid | stop_ma100_c1 | 2.0000 | 5.7711 | 0.4493 | 1.1719 | -0.3165 |
| 52 | stop_grid | stop_ma100_c2 | 2.0000 | 5.6623 | 0.4435 | 1.1603 | -0.3146 |
| 54 | stop_grid | stop_ma100_c3 | 2.0000 | 5.7038 | 0.4457 | 1.1636 | -0.3146 |
| 56 | stop_grid | stop_ma150_c1 | 2.0000 | 4.2832 | 0.3607 | 1.0583 | -0.3508 |
| 58 | stop_grid | stop_ma150_c2 | 2.0000 | 4.5721 | 0.3796 | 1.0924 | -0.3237 |
| 60 | stop_grid | stop_ma150_c3 | 2.0000 | 4.6694 | 0.3858 | 1.0961 | -0.3275 |
| 62 | stop_grid | stop_ma200_c1 | 2.0000 | 4.9544 | 0.4033 | 1.1515 | -0.3380 |
| 64 | stop_grid | stop_ma200_c2 | 2.0000 | 4.5429 | 0.3777 | 1.0942 | -0.3507 |
| 66 | stop_grid | stop_ma200_c3 | 2.0000 | 4.4383 | 0.3710 | 1.0790 | -0.3567 |
| 26 | stop_grid | stop_ma20_c1 | 2.0000 | 4.5887 | 0.3807 | 1.1219 | -0.3784 |
| 28 | stop_grid | stop_ma20_c2 | 2.0000 | 5.1584 | 0.4153 | 1.1096 | -0.3953 |
| 30 | stop_grid | stop_ma20_c3 | 2.0000 | 5.0318 | 0.4079 | 1.0840 | -0.3509 |
| 32 | stop_grid | stop_ma50_c1 | 2.0000 | 6.2084 | 0.4719 | 1.1767 | -0.3257 |
| 34 | stop_grid | stop_ma50_c2 | 2.0000 | 6.3507 | 0.4790 | 1.1855 | -0.3327 |
| 36 | stop_grid | stop_ma50_c3 | 2.0000 | 6.2074 | 0.4719 | 1.1718 | -0.3377 |
| 38 | stop_grid | stop_ma65_c1 | 2.0000 | 6.2886 | 0.4759 | 1.1862 | -0.3286 |
| 40 | stop_grid | stop_ma65_c2 | 2.0000 | 6.4046 | 0.4817 | 1.1935 | -0.3279 |
| 42 | stop_grid | stop_ma65_c3 | 2.0000 | 6.5491 | 0.4887 | 1.2027 | -0.3269 |
| 44 | stop_grid | stop_ma75_c1 | 2.0000 | 6.4891 | 0.4858 | 1.2044 | -0.3266 |
| 46 | stop_grid | stop_ma75_c2 | 2.0000 | 6.3998 | 0.4814 | 1.1936 | -0.3279 |
| 48 | stop_grid | stop_ma75_c3 | 2.0000 | 6.3719 | 0.4801 | 1.1891 | -0.3269 |
| 90 | trailing_confirm | trailing_lb11_c1 | 2.0000 | 2.5478 | 0.2190 | 0.7704 | -0.3669 |
| 92 | trailing_confirm | trailing_lb11_c2 | 2.0000 | 6.3719 | 0.4801 | 1.1891 | -0.3269 |
| 94 | trailing_confirm | trailing_lb11_c3 | 2.0000 | 5.8177 | 0.4518 | 1.0720 | -0.3407 |
| 96 | trailing_confirm | trailing_lb11_c5 | 2.0000 | 2.6615 | 0.2303 | 0.6930 | -0.4167 |
| 86 | trailing_grid | trailing_lb100_c2 | 2.0000 | 2.9081 | 0.2536 | 0.7198 | -0.4880 |
| 72 | trailing_grid | trailing_lb10_c2 | 2.0000 | 3.5199 | 0.3053 | 0.9025 | -0.3830 |
| 74 | trailing_grid | trailing_lb11_c2 | 2.0000 | 6.3719 | 0.4801 | 1.1891 | -0.3269 |
| 76 | trailing_grid | trailing_lb14_c2 | 2.0000 | 2.2890 | 0.1916 | 0.6326 | -0.4581 |
| 88 | trailing_grid | trailing_lb200_c2 | 2.0000 | 1.7400 | 0.1244 | 0.4835 | -0.5608 |
| 78 | trailing_grid | trailing_lb20_c2 | 2.0000 | 3.3683 | 0.2932 | 0.8211 | -0.4799 |
| 80 | trailing_grid | trailing_lb30_c2 | 2.0000 | 5.1799 | 0.4166 | 0.9825 | -0.4693 |
| 82 | trailing_grid | trailing_lb50_c2 | 2.0000 | 4.7237 | 0.3892 | 0.9430 | -0.4457 |
| 68 | trailing_grid | trailing_lb5_c2 | 2.0000 | 1.9007 | 0.1456 | 0.6898 | -0.3181 |
| 84 | trailing_grid | trailing_lb65_c2 | 2.0000 | 2.5561 | 0.2198 | 0.6619 | -0.5177 |
| 70 | trailing_grid | trailing_lb7_c2 | 2.0000 | 2.2171 | 0.1836 | 0.7630 | -0.2886 |
| 11 | core | btc_gate_immediate_reentry | 20.0000 | 1.3709 | 0.0691 | 0.3858 | -0.6120 |
| 5 | core | btc_gate_only | 20.0000 | 5.1658 | 0.4157 | 1.0693 | -0.3565 |
| 7 | core | full_current | 20.0000 | 5.5085 | 0.4351 | 1.1108 | -0.3456 |
| 13 | core | full_immediate_reentry | 20.0000 | 1.4919 | 0.0884 | 0.4178 | -0.5998 |
| 1 | core | no_overlay | 20.0000 | 2.4201 | 0.2058 | 0.6176 | -0.6747 |
| 9 | core | own_stop_immediate_reentry | 20.0000 | 2.2163 | 0.1835 | 0.5843 | -0.6274 |
| 3 | core | own_stop_only | 20.0000 | 2.3716 | 0.2006 | 0.6039 | -0.5802 |
| 23 | gate | gate_ma100 | 20.0000 | 2.4326 | 0.2071 | 0.6368 | -0.5124 |
| 17 | gate | gate_ma20 | 20.0000 | 2.0808 | 0.1678 | 0.5938 | -0.4423 |
| 25 | gate | gate_ma200 | 20.0000 | 2.0632 | 0.1657 | 0.5569 | -0.5556 |
| 19 | gate | gate_ma50 | 20.0000 | 2.8886 | 0.2518 | 0.7171 | -0.5388 |
| 21 | gate | gate_ma65 | 20.0000 | 2.0425 | 0.1632 | 0.5547 | -0.5893 |
| 15 | gate | gate_trailing11 | 20.0000 | 5.5085 | 0.4351 | 1.1108 | -0.3456 |
| 51 | stop_grid | stop_ma100_c1 | 20.0000 | 5.0175 | 0.4070 | 1.0933 | -0.3350 |
| 53 | stop_grid | stop_ma100_c2 | 20.0000 | 4.9171 | 0.4010 | 1.0811 | -0.3332 |
| 55 | stop_grid | stop_ma100_c3 | 20.0000 | 4.9496 | 0.4030 | 1.0840 | -0.3332 |
| 57 | stop_grid | stop_ma150_c1 | 20.0000 | 3.7494 | 0.3229 | 0.9772 | -0.3721 |
| 59 | stop_grid | stop_ma150_c2 | 20.0000 | 3.9962 | 0.3408 | 1.0110 | -0.3424 |
| 61 | stop_grid | stop_ma150_c3 | 20.0000 | 4.0791 | 0.3467 | 1.0155 | -0.3462 |
| 63 | stop_grid | stop_ma200_c1 | 20.0000 | 4.3562 | 0.3656 | 1.0727 | -0.3547 |
| 65 | stop_grid | stop_ma200_c2 | 20.0000 | 3.9890 | 0.3403 | 1.0151 | -0.3673 |
| 67 | stop_grid | stop_ma200_c3 | 20.0000 | 3.8926 | 0.3334 | 0.9993 | -0.3734 |
| 27 | stop_grid | stop_ma20_c1 | 20.0000 | 3.9530 | 0.3378 | 1.0285 | -0.4016 |
| 29 | stop_grid | stop_ma20_c2 | 20.0000 | 4.4375 | 0.3709 | 1.0246 | -0.4182 |
| 31 | stop_grid | stop_ma20_c3 | 20.0000 | 4.3270 | 0.3636 | 1.0001 | -0.3755 |
| 33 | stop_grid | stop_ma50_c1 | 20.0000 | 5.3546 | 0.4265 | 1.0970 | -0.3447 |
| 35 | stop_grid | stop_ma50_c2 | 20.0000 | 5.4760 | 0.4333 | 1.1060 | -0.3515 |
| 37 | stop_grid | stop_ma50_c3 | 20.0000 | 5.3518 | 0.4264 | 1.0924 | -0.3565 |
| 39 | stop_grid | stop_ma65_c1 | 20.0000 | 5.4395 | 0.4313 | 1.1078 | -0.3473 |
| 41 | stop_grid | stop_ma65_c2 | 20.0000 | 5.5339 | 0.4365 | 1.1148 | -0.3466 |
| 43 | stop_grid | stop_ma65_c3 | 20.0000 | 5.6588 | 0.4433 | 1.1243 | -0.3456 |
| 45 | stop_grid | stop_ma75_c1 | 20.0000 | 5.6187 | 0.4412 | 1.1264 | -0.3452 |
| 47 | stop_grid | stop_ma75_c2 | 20.0000 | 5.5356 | 0.4366 | 1.1154 | -0.3466 |
| 49 | stop_grid | stop_ma75_c3 | 20.0000 | 5.5085 | 0.4351 | 1.1108 | -0.3456 |
| 91 | trailing_confirm | trailing_lb11_c1 | 20.0000 | 2.1983 | 0.1815 | 0.6734 | -0.3885 |
| 93 | trailing_confirm | trailing_lb11_c2 | 20.0000 | 5.5085 | 0.4351 | 1.1108 | -0.3456 |
| 95 | trailing_confirm | trailing_lb11_c3 | 20.0000 | 5.0163 | 0.4070 | 0.9998 | -0.3456 |
| 97 | trailing_confirm | trailing_lb11_c5 | 20.0000 | 2.3029 | 0.1932 | 0.6218 | -0.4389 |
| 87 | trailing_grid | trailing_lb100_c2 | 20.0000 | 2.5594 | 0.2201 | 0.6609 | -0.5009 |
| 73 | trailing_grid | trailing_lb10_c2 | 20.0000 | 3.0456 | 0.2659 | 0.8195 | -0.3992 |
| 75 | trailing_grid | trailing_lb11_c2 | 20.0000 | 5.5085 | 0.4351 | 1.1108 | -0.3456 |
| 77 | trailing_grid | trailing_lb14_c2 | 20.0000 | 1.9754 | 0.1550 | 0.5556 | -0.4804 |
| 89 | trailing_grid | trailing_lb200_c2 | 20.0000 | 1.4936 | 0.0887 | 0.4177 | -0.5758 |
| 79 | trailing_grid | trailing_lb20_c2 | 20.0000 | 2.9225 | 0.2549 | 0.7493 | -0.4995 |
| 81 | trailing_grid | trailing_lb30_c2 | 20.0000 | 4.4704 | 0.3731 | 0.9151 | -0.4838 |
| 83 | trailing_grid | trailing_lb50_c2 | 20.0000 | 4.0919 | 0.3476 | 0.8769 | -0.4627 |
| 69 | trailing_grid | trailing_lb5_c2 | 20.0000 | 1.6476 | 0.1115 | 0.5623 | -0.3419 |
| 85 | trailing_grid | trailing_lb65_c2 | 20.0000 | 2.2379 | 0.1859 | 0.6001 | -0.5365 |
| 71 | trailing_grid | trailing_lb7_c2 | 20.0000 | 1.9199 | 0.1481 | 0.6487 | -0.2961 |

## Interpretation guardrails

- A variant is not promoted because it has the largest single-phase result.
- The current 75-day/3-day stop and 11-day BTC gate are inherited rules;
  this report tests whether they survive when separated from each other.
- Immediate re-entry is not assumed to be better. It must survive costs,
  turnover, and the phase-invariant basket comparison.
- The stop grid is a distribution audit. Selecting the maximum would be
  an overfit unless the result is supported by a broad parameter plateau.
