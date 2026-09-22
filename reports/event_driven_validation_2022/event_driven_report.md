# Daily Event-Driven Rotation Validation

## Research question

The previous champion only asked for a new leader every 21 days. This run tests daily
ranking with hysteresis: the incumbent is kept while it stays inside a hold-rank band,
and a switch requires either a confirmed rank deterioration or a challenger score gap.

All results are long-only, no leverage, T+1 execution, point-in-time Top-20, and use the
same BTC 11-day trailing gate with two-day confirmation as the champion.

## External evidence used to set the research direction

- Han, Kang, Ryu, *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market*:
  after realistic costs and daily marking, cross-sectional momentum is weak, time-series
  momentum is stronger, and momentum profits concentrate in large winners.
  <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>
- Yang, *Cryptocurrency market risk-managed momentum strategies*: risk scaling improved
  weekly return and Sharpe in crypto, with return enhancement rather than only downside protection.
  <https://doi.org/10.1016/j.frl.2025.107879>
- Kaya and Mostowfi, *Low-volatility strategies for highly liquid cryptocurrencies*: a simple
  stop-loss rule materially reduced downside risk and improved Sharpe.
  <https://doi.org/10.1016/j.frl.2021.102422>
- Alpha Architect tolerance-band research: reviewing more often is not the same as trading
  more often; a no-trade band reduced unnecessary trades.
  <https://alphaarchitect.com/destabilizing-rebalancing>
- Industry hysteresis implementation notes: enter above a high threshold, exit below a lower
  one, so small rank wobbles do not flip the portfolio.
  <https://aligrithm.com/percentile-rank-momentum-with-hysteresis-low-churn-signals>

## Method

- Daily point-in-time Top-20 snapshots are rebuilt from CMC market-cap data.
- CTREND-breakout scores are computed daily for the eligible universe.
- Fixed calendars are compared at 1/3/7/14/21/28/42/63 days.
- Event variants sweep minimum holding days, hold-rank bands, score gaps, and confirmation days.
- Costs are charged on actual target changes; a full switch has turnover 2.
- Rolling starts are monthly, with at least one year of remaining history.

## Fixed-calendar comparison

| index | variant_id | full_multiple_2bps | full_multiple_20bps | full_cagr_20bps | full_sharpe_20bps | full_max_drawdown_20bps | full_annualized_turnover | rolling20_median_rolling_start_multiple | rolling20_worst_rolling_start_multiple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | fixed_3D_immediate | 10.5776 | 4.8272 | 0.3956 | 0.7865 | -0.6563 | 92.0969 |  |  |
| 2 | fixed_3D_wait | 11.8600 | 5.7755 | 0.4496 | 0.8294 | -0.6071 | 84.4751 |  |  |
| 7 | fixed_14D_immediate | 3.9627 | 2.7285 | 0.2368 | 0.6370 | -0.7429 | 43.8254 |  |  |
| 8 | fixed_21D_wait | 21.5635 | 18.5674 | 0.8562 | 1.2491 | -0.5154 | 17.5725 |  |  |
| 6 | fixed_14D_wait | 4.0512 | 3.2809 | 0.2860 | 0.6931 | -0.7470 | 24.7709 |  |  |
| 9 | fixed_21D_immediate | 4.7006 | 3.3314 | 0.2902 | 0.6951 | -0.7435 | 40.4379 |  |  |
| 14 | fixed_63D_wait | 3.7672 | 3.5819 | 0.3101 | 0.8853 | -0.4106 | 5.9281 |  |  |
| 12 | fixed_42D_wait | 3.4404 | 3.1839 | 0.2779 | 0.7212 | -0.5501 | 9.1038 |  |  |
| 4 | fixed_7D_wait | 4.9240 | 3.2583 | 0.2841 | 0.6755 | -0.6148 | 48.4832 |  |  |
| 13 | fixed_42D_immediate | 2.1064 | 1.5816 | 0.1019 | 0.4593 | -0.6859 | 33.6630 |  |  |
| 10 | fixed_28D_wait | 0.8295 | 0.7418 | -0.0613 | 0.0706 | -0.7463 | 13.1265 |  |  |
| 5 | fixed_7D_immediate | 3.8121 | 2.1837 | 0.1798 | 0.5748 | -0.6266 | 65.4205 |  |  |
| 0 | fixed_1D_wait | 7.8812 | 1.7416 | 0.1246 | 0.5395 | -0.7149 | 177.2071 |  |  |
| 1 | fixed_1D_immediate | 7.8812 | 1.7416 | 0.1246 | 0.5395 | -0.7149 | 177.2071 |  |  |
| 15 | fixed_63D_immediate | 0.4611 | 0.3537 | -0.1975 | -0.0466 | -0.8420 | 31.1224 |  |  |
| 11 | fixed_28D_immediate | 0.1800 | 0.1308 | -0.3499 | -0.4334 | -0.9026 | 37.4739 |  |  |

## Top daily-event variants by rolling-start median

| index | variant_id | full_multiple_2bps | full_multiple_20bps | full_cagr_20bps | full_sharpe_20bps | full_max_drawdown_20bps | full_annualized_turnover | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling20_median_rolling_start_multiple | rolling20_worst_rolling_start_multiple | rolling20_worst_rolling_start_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 94 | event_mh5_hr2_gap0p1_c1 | 137.4284 | 76.4827 | 1.5049 | 1.4502 | -0.6111 | 68.8080 | 2.8924 | 0.6453 | 51.5190 | 1.4638 | -0.6114 |
| 53 | event_mh3_hr1_gap0p05_c2 | 13.3536 | 5.7939 | 0.4506 | 0.8307 | -0.6964 | 98.0249 | 2.5521 | 0.3570 | 6.8181 | 0.5244 | -0.6964 |
| 92 | event_mh5_hr2_gap0p05_c1 | 24.9513 | 13.0600 | 0.7229 | 1.0475 | -0.6047 | 76.0064 | 2.5296 | 0.4408 | 13.0600 | 0.8927 | -0.6248 |
| 100 | event_mh5_hr3_gap0p05_c1 | 5.9255 | 3.1694 | 0.2766 | 0.6828 | -0.7834 | 73.4658 | 2.3665 | 0.2762 |  |  |  |
| 55 | event_mh3_hr1_gap0p1_c2 | 17.6805 | 7.9244 | 0.5500 | 0.8978 | -0.6853 | 94.2140 | 2.2214 | 0.4068 |  |  |  |
| 108 | event_mh5_hr5_gap0p05_c1 | 4.5771 | 2.4481 | 0.2087 | 0.6143 | -0.8085 | 73.4658 | 2.2191 | 0.2442 |  |  |  |
| 109 | event_mh5_hr5_gap0p05_c2 | 4.5771 | 2.4481 | 0.2087 | 0.6143 | -0.8085 | 73.4658 | 2.2191 | 0.2442 |  |  |  |
| 101 | event_mh5_hr3_gap0p05_c2 | 4.5771 | 2.4481 | 0.2087 | 0.6143 | -0.8085 | 73.4658 | 2.2191 | 0.2442 |  |  |  |
| 30 | event_mh0_hr2_gap0p1_c1 | 23.5723 | 9.7589 | 0.6198 | 0.9677 | -0.6908 | 103.5296 | 2.0072 | 0.4247 |  |  |  |
| 87 | event_mh5_hr1_gap0p1_c2 | 32.9139 | 16.5575 | 0.8117 | 1.0706 | -0.6813 | 80.6642 | 1.9867 | 0.4382 |  |  |  |
| 61 | event_mh3_hr2_gap0p05_c2 | 6.5448 | 3.2103 | 0.2801 | 0.6842 | -0.7220 | 83.6282 | 1.9842 | 0.3318 |  |  |  |
| 62 | event_mh3_hr2_gap0p1_c1 | 9.6996 | 4.7065 | 0.3881 | 0.7777 | -0.6949 | 84.8985 | 1.9151 | 0.4491 |  |  |  |
| 68 | event_mh3_hr3_gap0p05_c1 | 6.6553 | 3.2763 | 0.2856 | 0.6889 | -0.7186 | 83.2048 | 1.8471 | 0.3422 |  |  |  |
| 23 | event_mh0_hr1_gap0p1_c2 | 16.7054 | 6.7436 | 0.4979 | 0.8572 | -0.6796 | 106.4936 | 1.8436 | 0.4660 |  |  |  |
| 85 | event_mh5_hr1_gap0p05_c2 | 21.2979 | 10.6754 | 0.6509 | 0.9709 | -0.7562 | 81.0876 | 1.8359 | 0.3546 |  |  |  |
| 60 | event_mh3_hr2_gap0p05_c1 | 6.2196 | 2.8900 | 0.2519 | 0.6613 | -0.6917 | 89.9797 | 1.8046 | 0.4031 |  |  |  |
| 69 | event_mh3_hr3_gap0p05_c2 | 4.6390 | 2.2919 | 0.1920 | 0.6001 | -0.7421 | 82.7813 | 1.7783 | 0.3136 |  |  |  |
| 77 | event_mh3_hr5_gap0p05_c2 | 4.5889 | 2.2672 | 0.1892 | 0.5976 | -0.7449 | 82.7813 | 1.7597 | 0.3136 |  |  |  |
| 76 | event_mh3_hr5_gap0p05_c1 | 4.5889 | 2.2672 | 0.1892 | 0.5976 | -0.7449 | 82.7813 | 1.7597 | 0.3136 |  |  |  |
| 29 | event_mh0_hr2_gap0p05_c2 | 8.1755 | 3.4463 | 0.2995 | 0.7049 | -0.7361 | 101.4124 | 1.7227 | 0.3303 |  |  |  |

## Hybrid 21-day selection + daily rank-stop exits

| index | variant_id | full_multiple_2bps | full_multiple_20bps | full_cagr_20bps | full_sharpe_20bps | full_max_drawdown_20bps | full_annualized_turnover | rolling_1y_median_multiple | rolling_1y_worst_multiple | rolling20_median_rolling_start_multiple | rolling20_worst_rolling_start_multiple | rolling20_worst_rolling_start_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 211 | rankstop_21D_hr5_c3_mh10 | 29.3084 | 25.3269 | 0.9823 | 1.2377 | -0.5779 | 17.1491 | 1.9070 | 0.6230 |  |  |  |
| 210 | rankstop_21D_hr5_c3_mh5 | 25.3218 | 21.8819 | 0.9218 | 1.2010 | -0.5779 | 17.1491 | 1.8072 | 0.6361 |  |  |  |
| 209 | rankstop_21D_hr5_c3_mh0 | 25.0687 | 21.6632 | 0.9178 | 1.1982 | -0.5779 | 17.1491 | 1.8047 | 0.6361 |  |  |  |
| 202 | rankstop_21D_hr3_c3_mh10 | 24.9434 | 21.5551 | 0.9157 | 1.2563 | -0.6554 | 17.1491 | 1.5392 | 0.3866 |  |  |  |
| 184 | rankstop_21D_hr1_c3_mh10 | 11.0767 | 9.5724 | 0.6132 | 1.0866 | -0.5461 | 17.1491 | 1.4374 | 0.5005 |  |  |  |
| 196 | rankstop_21D_hr3_c1_mh10 | 12.1376 | 10.4891 | 0.6448 | 1.0845 | -0.5054 | 17.1491 | 1.4299 | 0.5568 |  |  |  |
| 199 | rankstop_21D_hr3_c2_mh10 | 18.9171 | 16.3477 | 0.8068 | 1.1952 | -0.5567 | 17.1491 | 1.4287 | 0.4693 |  |  |  |
| 187 | rankstop_21D_hr2_c1_mh10 | 8.5030 | 7.3482 | 0.5254 | 0.9920 | -0.5369 | 17.1491 | 1.3852 | 0.5120 |  |  |  |
| 208 | rankstop_21D_hr5_c2_mh10 | 17.3771 | 15.0164 | 0.7746 | 1.1449 | -0.6609 | 17.1491 | 1.3844 | 0.3743 |  |  |  |
| 205 | rankstop_21D_hr5_c1_mh10 | 14.1334 | 12.2135 | 0.6986 | 1.0936 | -0.6702 | 17.1491 | 1.3780 | 0.3641 |  |  |  |
| 190 | rankstop_21D_hr2_c2_mh10 | 17.4568 | 15.0858 | 0.7763 | 1.1986 | -0.5760 | 17.1491 | 1.3739 | 0.4430 |  |  |  |
| 200 | rankstop_21D_hr3_c3_mh0 | 13.9598 | 12.0635 | 0.6942 | 1.0943 | -0.6550 | 17.1491 | 1.3615 | 0.3736 |  |  |  |
| 201 | rankstop_21D_hr3_c3_mh5 | 13.4539 | 11.6264 | 0.6810 | 1.0822 | -0.6550 | 17.1491 | 1.3446 | 0.3736 |  |  |  |
| 181 | rankstop_21D_hr1_c2_mh10 | 6.9378 | 5.9740 | 0.4600 | 0.9222 | -0.5594 | 17.5725 | 1.3435 | 0.5199 |  |  |  |
| 178 | rankstop_21D_hr1_c1_mh10 | 7.0386 | 6.0608 | 0.4645 | 0.9282 | -0.5318 | 17.5725 | 1.3296 | 0.5199 |  |  |  |
| 193 | rankstop_21D_hr2_c3_mh10 | 18.3252 | 15.8360 | 0.7947 | 1.1930 | -0.5631 | 17.1491 | 1.3230 | 0.4835 |  |  |  |
| 191 | rankstop_21D_hr2_c3_mh0 | 6.5387 | 5.6506 | 0.4429 | 0.8902 | -0.5827 | 17.1491 | 1.2773 | 0.4518 |  |  |  |
| 192 | rankstop_21D_hr2_c3_mh5 | 6.2656 | 5.4146 | 0.4299 | 0.8746 | -0.5827 | 17.1491 | 1.2627 | 0.4518 |  |  |  |
| 186 | rankstop_21D_hr2_c1_mh5 | 5.0919 | 4.4003 | 0.3685 | 0.8425 | -0.5710 | 17.1491 | 1.2578 | 0.4721 |  |  |  |
| 207 | rankstop_21D_hr5_c2_mh5 | 10.5510 | 9.1176 | 0.5967 | 1.0108 | -0.6754 | 17.1491 | 1.2405 | 0.3583 |  |  |  |

## Selected event candidate

- Variant: `event_mh5_hr2_gap0p1_c1`
- Minimum hold: 5 days
- Hold-rank band: top 2
- Score gap: 10.00%
- Confirmation: 1 day(s)
- Latest target: `avalanche-2`

## Yearly returns for selected candidate

| index | year | strategy | btc |
| --- | --- | --- | --- |
| 0 | 2,022.0000 | -0.3467 | -0.6531 |
| 1 | 2,023.0000 | 1.6890 | 1.5542 |
| 2 | 2,024.0000 | 21.6088 | 1.2105 |
| 3 | 2,025.0000 | 0.3752 | -0.0634 |
| 4 | 2,026.0000 | 0.4003 | -0.0104 |

## BTC benchmark

- BTC 2bps multiple: 1.82x
- BTC CAGR: 13.46%
- BTC Sharpe: 0.502
- BTC max drawdown: -66.90%

## Interpretation guardrails

- A higher full-window multiple is not sufficient; the rolling-start median and worst
  start must improve together with cost survival.
- Daily checking is not automatically better. It is only useful if the trigger avoids
  noise trades and the added reaction speed compensates for the extra turnover.
- These results are historical simulations, not a live-trading guarantee.
