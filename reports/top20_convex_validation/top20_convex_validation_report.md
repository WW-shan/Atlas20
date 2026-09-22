# Top20 Convex Leader Validation

## Notes

- Raw and robust screening rankings are full-screen rankings from the full-window screen.
- Full-window screening scores are separate from validated subset diagnostics.
- Validated robustness is only shown after merging rolling-start, 100 bps cost, and stability diagnostics for selected validation candidates.
- This report is research output only and does not execute trades.

## Best Raw Convexity Candidate

| index | candidate_id | family_id | strategy_kind | top_n | frequency | liquidity_label | multiple | cagr | sharpe | max_drawdown | screening_raw_convexity_score | raw_convexity_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | ctrend_lite | ctrend_lite | 1.0000 | 21D | strict | 564.77 | 202.57% | 1.62 | -73.09% | -2.44 | -2.44 |

## Best Screening Robust Candidate

| index | candidate_id | family_id | strategy_kind | top_n | frequency | liquidity_label | multiple | cagr | sharpe | max_drawdown | screening_robust_convexity_score | robust_convexity_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | ctrend_lite | ctrend_lite | 1.0000 | 21D | strict | 564.77 | 202.57% | 1.62 | -73.09% | 1.75 | 0.21 |

## Validated Candidate Diagnostics

| index | candidate_id | family_id | multiple | screening_robust_convexity_score | validated_robust_convexity_score | median_rolling_start_multiple | cost_survival_100bps | stability_score | start_count | neighbor_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | ctrend_lite__ctrend_lite__top2__7d__ctrend_lite_relative_strength__strict__ex_btc__btc_ma_defensive | ctrend_lite | 179.43 | 1.42 | 0.50 | 6.81 | 17.59% | 34.80% | 57.00 | 20.00 |
| 1 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop11 | champion_ablation | 17.33 | 0.68 | 0.45 | 5.16 | 22.41% | 100.00% | 57.00 | 1.00 |
| 2 | ctrend_lite__ctrend_lite__top2__7d__ctrend_lite_relative_strength__loose__ex_btc__btc_ma_defensive | ctrend_lite | 149.62 | 1.36 | 0.45 | 5.65 | 16.95% | 41.94% | 57.00 | 21.00 |
| 3 | ctrend_lite__ctrend_lite__top2__7d__ctrend_lite_relative_strength__medium__ex_btc__btc_ma_defensive | ctrend_lite | 149.62 | 1.36 | 0.45 | 5.65 | 16.95% | 41.94% | 57.00 | 21.00 |
| 4 | ctrend_lite__ctrend_lite__top3__7d__ctrend_lite_relative_strength__strict__with_btc__btc_ma_defensive | ctrend_lite | 201.59 | 1.46 | 0.44 | 5.54 | 19.95% | 34.72% | 57.00 | 15.00 |
| 5 | ctrend_lite__ctrend_lite__top3__7d__ctrend_lite_relative_strength__strict__ex_btc__btc_ma_defensive | ctrend_lite | 293.59 | 1.57 | 0.44 | 5.53 | 20.51% | 22.43% | 57.00 | 15.00 |
| 6 | ctrend_lite__ctrend_lite__top3__7d__ctrend_lite_balanced__strict__with_btc__btc_ma_defensive | ctrend_lite | 222.22 | 1.48 | 0.42 | 5.27 | 18.38% | 31.50% | 57.00 | 15.00 |
| 7 | ctrend_lite__ctrend_lite__top3__7d__ctrend_lite_relative_strength__loose__with_btc__btc_ma_defensive | ctrend_lite | 186.22 | 1.43 | 0.42 | 5.04 | 19.58% | 38.49% | 57.00 | 15.00 |
| 8 | ctrend_lite__ctrend_lite__top3__7d__ctrend_lite_relative_strength__medium__with_btc__btc_ma_defensive | ctrend_lite | 186.22 | 1.43 | 0.42 | 5.01 | 19.58% | 38.49% | 57.00 | 15.00 |
| 9 | ctrend_lite__ctrend_lite__top3__7d__ctrend_lite_relative_strength__medium__ex_btc__btc_ma_defensive | ctrend_lite | 265.83 | 1.54 | 0.41 | 5.10 | 20.12% | 23.98% | 57.00 | 15.00 |

## 100x Rolling Windows

| index | candidate_id | window_label | window_end | multiple |
| --- | --- | --- | --- | --- |
| 0 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2025-12-30 00:00:00 | 258.81 |
| 1 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2025-12-31 00:00:00 | 258.81 |
| 2 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-01 00:00:00 | 257.04 |
| 3 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-02 00:00:00 | 238.88 |
| 4 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-03 00:00:00 | 240.18 |
| 5 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-04 00:00:00 | 235.53 |
| 6 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-05 00:00:00 | 233.12 |
| 7 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-06 00:00:00 | 226.23 |
| 8 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-07 00:00:00 | 231.86 |
| 9 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-08 00:00:00 | 223.74 |
| 10 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-09 00:00:00 | 231.57 |
| 11 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-10 00:00:00 | 256.17 |
| 12 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-11 00:00:00 | 257.92 |
| 13 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-12 00:00:00 | 244.91 |
| 14 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-13 00:00:00 | 235.20 |
| 15 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-14 00:00:00 | 240.22 |
| 16 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-15 00:00:00 | 227.69 |
| 17 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-16 00:00:00 | 215.16 |
| 18 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-17 00:00:00 | 216.74 |
| 19 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-18 00:00:00 | 229.74 |
| 20 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-19 00:00:00 | 230.71 |
| 21 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-20 00:00:00 | 254.35 |
| 22 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-21 00:00:00 | 240.58 |
| 23 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-22 00:00:00 | 222.91 |
| 24 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 5y | 2026-01-23 00:00:00 | 232.19 |

## Rolling-Start Diagnostics

| index | candidate_id | start_count | median_rolling_start_multiple | min_rolling_start_multiple | max_rolling_start_multiple | max_rolling_start_drawdown | median_rolling_start_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop11 | 57.00 | 5.16 | 0.46 | 67.96 | -0.8292 | -0.7281 |
| 1 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 57.00 | 2.60 | 0.21 | 564.77 | -0.9077 | -0.6462 |
| 2 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__loose__ex_btc__btc_ma_defensive | 57.00 | 2.60 | 0.21 | 472.63 | -0.9077 | -0.6462 |
| 3 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__medium__ex_btc__btc_ma_defensive | 57.00 | 2.60 | 0.21 | 472.63 | -0.9077 | -0.6462 |
| 4 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__loose__with_btc__btc_ma_defensive | 57.00 | 2.51 | 0.38 | 421.60 | -0.8580 | -0.6488 |
| 5 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__medium__with_btc__btc_ma_defensive | 57.00 | 2.51 | 0.38 | 421.60 | -0.8580 | -0.6488 |
| 6 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__strict__with_btc__btc_ma_defensive | 57.00 | 2.56 | 0.38 | 421.60 | -0.8580 | -0.6488 |
| 7 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__loose__with_btc__btc_ma_defensive | 57.00 | 2.46 | 0.25 | 409.64 | -0.8989 | -0.6446 |
| 8 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__medium__with_btc__btc_ma_defensive | 57.00 | 2.46 | 0.25 | 409.64 | -0.8989 | -0.6446 |
| 9 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__with_btc__btc_ma_defensive | 57.00 | 2.46 | 0.25 | 409.64 | -0.8703 | -0.6446 |

## Cost Sensitivity

| index | candidate_id | total_cost_bps | base_multiple | stressed_multiple | survival_ratio |
| --- | --- | --- | --- | --- | --- |
| 0 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop11 | 20.00 | 17.33 | 17.33 | 100.00% |
| 1 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__loose__ex_btc__btc_ma_defensive | 20.00 | 179.99 | 179.99 | 100.00% |
| 2 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__loose__with_btc__btc_ma_defensive | 20.00 | 421.60 | 421.60 | 100.00% |
| 3 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__medium__ex_btc__btc_ma_defensive | 20.00 | 179.99 | 179.99 | 100.00% |
| 4 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__medium__with_btc__btc_ma_defensive | 20.00 | 421.60 | 421.60 | 100.00% |
| 5 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 20.00 | 228.74 | 228.74 | 100.00% |
| 6 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__strict__with_btc__btc_ma_defensive | 20.00 | 421.60 | 421.60 | 100.00% |
| 7 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__loose__ex_btc__btc_ma_defensive | 20.00 | 472.63 | 472.63 | 100.00% |
| 8 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__loose__with_btc__btc_ma_defensive | 20.00 | 409.64 | 409.64 | 100.00% |
| 9 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__medium__ex_btc__btc_ma_defensive | 20.00 | 472.63 | 472.63 | 100.00% |

## Stability Surface

| index | candidate_id | neighbor_count | median_neighbor_multiple | stability_score |
| --- | --- | --- | --- | --- |
| 0 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop11 | 1.00 | 28.73 | 100.00% |
| 1 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | 14.00 | 78.93 | 13.98% |
| 2 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__loose__ex_btc__btc_ma_defensive | 14.00 | 73.72 | 15.60% |
| 3 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__medium__ex_btc__btc_ma_defensive | 14.00 | 73.72 | 15.60% |
| 4 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__loose__with_btc__btc_ma_defensive | 22.00 | 69.09 | 16.39% |
| 5 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__medium__with_btc__btc_ma_defensive | 22.00 | 69.09 | 16.39% |
| 6 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__strict__with_btc__btc_ma_defensive | 22.00 | 64.31 | 15.25% |
| 7 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__loose__with_btc__btc_ma_defensive | 14.00 | 81.77 | 19.96% |
| 8 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__medium__with_btc__btc_ma_defensive | 14.00 | 81.77 | 19.96% |
| 9 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__with_btc__btc_ma_defensive | 14.00 | 93.53 | 22.83% |

## Contribution Concentration

| index | candidate_id | top_coin_id | top1_contribution_share | top3_contribution_share | top5_contribution_share |
| --- | --- | --- | --- | --- | --- |
| 0 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop11 | bitcoin | 22.46% | 44.64% | 64.91% |
| 1 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__ex_btc__btc_ma_defensive | binancecoin | 13.07% | 37.82% | 60.24% |
| 2 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__loose__ex_btc__btc_ma_defensive | binancecoin | 13.13% | 38.01% | 60.54% |
| 3 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__medium__ex_btc__btc_ma_defensive | binancecoin | 13.13% | 38.01% | 60.54% |
| 4 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__loose__with_btc__btc_ma_defensive | tron | 20.01% | 44.35% | 63.98% |
| 5 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__medium__with_btc__btc_ma_defensive | tron | 20.01% | 44.35% | 63.98% |
| 6 | ctrend_lite__ctrend_lite__top1__14d__ctrend_lite_acceleration__strict__with_btc__btc_ma_defensive | tron | 20.01% | 44.35% | 63.98% |
| 7 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__loose__with_btc__btc_ma_defensive | binancecoin | 12.82% | 38.25% | 60.83% |
| 8 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__medium__with_btc__btc_ma_defensive | binancecoin | 12.82% | 38.25% | 60.83% |
| 9 | ctrend_lite__ctrend_lite__top1__21d__ctrend_lite_acceleration__strict__with_btc__btc_ma_defensive | binancecoin | 12.82% | 38.25% | 60.83% |

## Champion Ablation

| index | candidate_id | overlay_set | stop_lookback | multiple | cagr | sharpe | max_drawdown | raw_convexity_score | robust_convexity_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | champion_ablation__leader_momentum__top1__7d__base__loose__with_btc__champion_ablation_stop11 | champion_ablation_stop11 | 11.0000 | 28.73 | 79.80% | 1.05 | -84.52% | -3.80 | 0.82 |
| 1 | champion_ablation__leader_momentum__top1__28d__base__loose__with_btc__champion_ablation_stop11 | champion_ablation_stop11 | 11.0000 | 26.07 | 76.78% | 1.09 | -79.10% | -3.83 | 0.81 |
| 2 | champion_ablation__leader_momentum__top1__21d__base__loose__with_btc__champion_ablation_stop11 | champion_ablation_stop11 | 11.0000 | 20.93 | 70.13% | 1.02 | -78.87% | -3.93 | 0.74 |
| 3 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop13 | champion_ablation_stop13 | 13.0000 | 19.57 | 68.14% | 1.00 | -79.55% | -3.96 | 0.72 |
| 4 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_confirm3 | champion_ablation_confirm3 | 11.0000 | 18.08 | 65.84% | 0.99 | -79.88% | -4.00 | 0.69 |
| 5 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop10 | champion_ablation_stop10 | 10.0000 | 17.45 | 64.81% | 0.99 | -80.88% | -4.02 | 0.68 |
| 6 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop11 | champion_ablation_stop11 | 11.0000 | 17.33 | 64.61% | 0.99 | -79.34% | -4.02 | 0.45 |
| 7 | champion_ablation__leader_momentum__top1__14d__base__medium__with_btc__champion_ablation_stop11 | champion_ablation_stop11 | 11.0000 | 17.33 | 64.61% | 0.99 | -79.34% | -4.02 | 0.68 |
| 8 | champion_ablation__leader_momentum__top1__14d__base__loose__ex_btc__champion_ablation_stop11 | champion_ablation_stop11 | 11.0000 | 17.23 | 64.45% | 0.98 | -79.45% | -4.02 | 0.68 |
| 9 | champion_ablation__leader_momentum__top1__14d__base__loose__with_btc__champion_ablation_stop12 | champion_ablation_stop12 | 12.0000 | 17.01 | 64.07% | 0.98 | -79.50% | -4.02 | 0.67 |
