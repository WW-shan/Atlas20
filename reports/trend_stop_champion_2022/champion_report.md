# CTREND Top20 + Daily Own-Trend Stop — 2022 Start

> **Research upper tail, not production-ready.** The headline result is tied to the
> 2022-01-01 rebalance phase, and the inherited 11-day/two-day BTC gate is a local
> parameter spike. See `PHASE_WARNING.md` and
> `reports/decision_point_ablation_2022/` before using these numbers.

This is the final candidate from the daily-rebalancing research. The coin ranking remains
on the original 21-day schedule; the daily check is used to exit the holding after three
consecutive closes below its own 75-day moving average. Re-entry waits for the next
scheduled decision.

## Summary

| index | candidate_id | total_cost_bps | leverage | total_return | cagr | annualized_volatility | sharpe | sortino | max_drawdown | calmar | monthly_win_rate | annualized_turnover | avg_turnover_per_rebalance | average_holdings | multiple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | CTREND_TREND_STOP_2bps | 2.0000 | 1.0000 | 24.8685 | 0.9912 | 0.6504 | 1.3599 | 2.8483 | -0.4179 | 2.3720 | 0.3860 | 16.7256 | 1.1127 | 0.2719 | 25.8685 |
| 1 | CTREND_TREND_STOP_5bps | 5.0000 | 1.0000 | 24.2624 | 0.9812 | 0.6504 | 1.3522 | 2.8310 | -0.4193 | 2.3400 | 0.3860 | 16.7256 | 1.1127 | 0.2719 | 25.2624 |
| 2 | CTREND_TREND_STOP_10bps | 10.0000 | 1.0000 | 23.2831 | 0.9647 | 0.6504 | 1.3393 | 2.8022 | -0.4262 | 2.2632 | 0.3860 | 16.7256 | 1.1127 | 0.2719 | 24.2831 |
| 3 | CTREND_TREND_STOP_20bps | 20.0000 | 1.0000 | 21.4353 | 0.9320 | 0.6505 | 1.3134 | 2.7443 | -0.4399 | 2.1189 | 0.3860 | 16.7256 | 1.1127 | 0.2719 | 22.4353 |
| 4 | CTREND_TREND_STOP_50bps | 50.0000 | 1.0000 | 16.6836 | 0.8371 | 0.6510 | 1.2356 | 2.5697 | -0.4789 | 1.7478 | 0.3684 | 16.7256 | 1.1127 | 0.2719 | 17.6836 |
| 5 | CTREND_TREND_STOP_100bps | 100.0000 | 1.0000 | 10.8702 | 0.6884 | 0.6523 | 1.1050 | 2.2763 | -0.5384 | 1.2787 | 0.2982 | 16.7256 | 1.1127 | 0.2719 | 11.8702 |
| 6 | BTC_BH_2bps | 2.0000 | 1.0000 | 0.8157 | 0.1346 | 0.5080 | 0.5025 | 0.8431 | -0.6690 | 0.2012 | 0.5614 | 0.2117 | 1.0000 | 0.9994 | 1.8157 |

## Yearly Returns

| index | year | CTREND_TREND_STOP_2bps |
| --- | --- | --- |
| 0 | 2022-12-31 00:00:00 | -0.0585 |
| 1 | 2023-12-31 00:00:00 | 0.6667 |
| 2 | 2024-12-31 00:00:00 | 3.4722 |
| 3 | 2025-12-31 00:00:00 | 0.4272 |
| 4 | 2026-12-31 00:00:00 | 1.5828 |

## Subperiods

| index | period | total_return | cagr | annualized_volatility | sharpe | sortino | max_drawdown | calmar | monthly_win_rate | annualized_turnover | avg_turnover_per_rebalance | average_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2022 | -0.0585 | -0.0587 | 0.4960 | 0.1176 | 0.2074 | -0.2926 | -0.2005 | 0.1667 | 14.0385 | 1.0769 | 0.1973 |
| 1 | 2023 | 0.6667 | 0.6690 | 0.5862 | 1.1508 | 2.2006 | -0.4179 | 1.6010 | 0.4167 | 20.0549 | 1.1765 | 0.3123 |
| 2 | 2024 | 3.4722 | 3.4722 | 1.0059 | 1.9378 | 4.5413 | -0.3680 | 9.4342 | 0.4167 | 18.0000 | 1.1250 | 0.3415 |
| 3 | 2025 | 0.4272 | 0.4286 | 0.3441 | 1.2028 | 2.1468 | -0.1957 | 2.1902 | 0.3333 | 14.0385 | 1.1667 | 0.2384 |
| 4 | 2026_ytd | 1.5828 | 2.7318 | 0.6109 | 2.4412 | 5.3378 | -0.1807 | 15.1203 | 0.6667 | 18.0418 | 1.0000 | 0.2689 |

The daily leader-rotation alternatives were not adopted: the highest fixed-start result
was a narrow parameter spike, and the more stable event variants did not improve the
rolling-start distribution enough to justify their much higher turnover.
