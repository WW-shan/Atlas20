# CTREND Top20 Champion — 2022 Start

This is a real point-in-time Top20, long-only, unlevered simulation. The primary cost case is 2bps round-trip (the desk's stated venue cost plus rebate), with 20bps shown as a conservative stress case. The strategy exits to cash when BTC loses its 11-day trailing level for two consecutive closes and only re-enters at the next 21-day scheduled decision.

## Summary

| index | candidate_id | total_cost_bps | leverage | total_return | cagr | annualized_volatility | sharpe | sortino | max_drawdown | calmar | monthly_win_rate | annualized_turnover | avg_turnover_per_rebalance | average_holdings | multiple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | CTREND_TOP20_CHAMPION_2bps | 2.0000 | 1.0000 | 20.5635 | 0.9159 | 0.6533 | 1.2978 | 2.6974 | -0.4922 | 1.8608 | 0.4035 | 17.5725 | 1.1067 | 0.2870 | 21.5635 |
| 1 | CTREND_TOP20_CHAMPION_5bps | 5.0000 | 1.0000 | 20.0330 | 0.9058 | 0.6533 | 1.2897 | 2.6796 | -0.4961 | 1.8257 | 0.4035 | 17.5725 | 1.1067 | 0.2870 | 21.0330 |
| 2 | CTREND_TOP20_CHAMPION_10bps | 10.0000 | 1.0000 | 19.1772 | 0.8891 | 0.6534 | 1.2762 | 2.6499 | -0.5027 | 1.7689 | 0.4035 | 17.5725 | 1.1067 | 0.2870 | 20.1772 |
| 3 | CTREND_TOP20_CHAMPION_20bps | 20.0000 | 1.0000 | 17.5674 | 0.8562 | 0.6535 | 1.2491 | 2.5904 | -0.5154 | 1.6610 | 0.4035 | 17.5725 | 1.1067 | 0.2870 | 18.5674 |
| 4 | CTREND_TOP20_CHAMPION_50bps | 50.0000 | 1.0000 | 13.4596 | 0.7605 | 0.6539 | 1.1678 | 2.4111 | -0.5520 | 1.3777 | 0.3860 | 17.5725 | 1.1067 | 0.2870 | 14.4596 |
| 5 | CTREND_TOP20_CHAMPION_100bps | 100.0000 | 1.0000 | 8.5125 | 0.6111 | 0.6553 | 1.0314 | 2.1100 | -0.6071 | 1.0067 | 0.3158 | 17.5725 | 1.1067 | 0.2870 | 9.5125 |
| 6 | BTC_BH_2bps | 2.0000 | 1.0000 | 0.8157 | 0.1346 | 0.5080 | 0.5025 | 0.8431 | -0.6690 | 0.2012 | 0.5614 | 0.2117 | 1.0000 | 0.9994 | 1.8157 |

## Yearly Returns

| index | year | CTREND_TOP20_CHAMPION_2bps |
| --- | --- | --- |
| 0 | 2022-12-31 00:00:00 | -0.1826 |
| 1 | 2023-12-31 00:00:00 | 0.6667 |
| 2 | 2024-12-31 00:00:00 | 3.4722 |
| 3 | 2025-12-31 00:00:00 | 0.3703 |
| 4 | 2026-12-31 00:00:00 | 1.5828 |

## Subperiods

| index | period | total_return | cagr | annualized_volatility | sharpe | sortino | max_drawdown | calmar | monthly_win_rate | annualized_turnover | avg_turnover_per_rebalance | average_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2022 | -0.1826 | -0.1830 | 0.5099 | -0.1485 | -0.2533 | -0.3313 | -0.5525 | 0.2500 | 16.0440 | 1.0667 | 0.2466 |
| 1 | 2023 | 0.6667 | 0.6690 | 0.5862 | 1.1508 | 2.2006 | -0.4179 | 1.6010 | 0.4167 | 20.0549 | 1.1765 | 0.3123 |
| 2 | 2024 | 3.4722 | 3.4722 | 1.0059 | 1.9378 | 4.5413 | -0.3680 | 9.4342 | 0.4167 | 18.0000 | 1.1250 | 0.3415 |
| 3 | 2025 | 0.3703 | 0.3715 | 0.3491 | 1.0737 | 1.9068 | -0.1957 | 1.8983 | 0.3333 | 16.0440 | 1.1429 | 0.2603 |
| 4 | 2026_ytd | 1.5828 | 2.7318 | 0.6109 | 2.4412 | 5.3378 | -0.1807 | 15.1203 | 0.6667 | 18.0418 | 1.0000 | 0.2689 |

This report deliberately does not claim that the 20x target is repeatable. The accompanying rolling-start diagnostics show a wide dispersion across entry dates.
