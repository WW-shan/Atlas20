# PR2026-11-LS102-LS101-ROBUSTNESS

LS102 does not change LS101. It audits the frozen 100% residual candidate under
additional basis cost, year, rolling-window and monthly-start stress.

- Sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00
- LS57 baseline: 68.8077x / Sharpe 1.9819 / MDD -39.8350%
- Rolling window: 365 daily observations; required win rate 75%
- Required worst terminal shortfall <= 2.0%; required MDD delta <= 2.0%

## Cost stress

| index | cost_bps | multiple | sharpe | max_drawdown | baseline_multiple | baseline_sharpe | passes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 10.0000 | 73.7400 | 2.0110 | -0.3995 | 68.8077 | 1.9819 | 1.0000 |
| 1 | 20.0000 | 69.4617 | 1.9873 | -0.4053 | 68.8077 | 1.9819 | 1.0000 |
| 2 | 50.0000 | 58.0510 | 1.9159 | -0.4223 | 68.8077 | 1.9819 | 0.0000 |
| 3 | 100.0000 | 43.0234 | 1.7958 | -0.4496 | 68.8077 | 1.9819 | 0.0000 |

## Frozen checks

| index | check | value | status |
| --- | --- | --- | --- |
| 0 | cost_010 | True | pass |
| 1 | cost_020 | True | pass |
| 2 | cost_050 | False | fail |
| 3 | cost_100 | False | fail |
| 4 | yearly_4_of_5 | True | pass |
| 5 | best_year_removed | True | pass |
| 6 | rolling_win_rate | True | pass |
| 7 | rolling_worst_terminal | True | pass |
| 8 | rolling_mdd_delta | True | pass |
| 9 | monthly_win_rate | True | pass |
| 10 | monthly_mdd_delta | True | pass |
| 11 | gross_cap | True | pass |
| 12 | finite | True | pass |
| 13 | yearly_wins | 5 | info |
| 14 | best_year | 2024 | info |
| 15 | rolling_win_rate | 0.9419117647058823 | info |
| 16 | rolling_worst_excess | -0.007737626526926444 | info |
| 17 | rolling_mdd_delta | 0.008153059786410677 | info |
| 18 | monthly_win_rate | 0.9814814814814815 | info |
| 19 | monthly_mdd_delta | 0.004854381062908475 | info |
| 20 | max_gross | 1.45 | info |

## Yearly comparison

| index | year | candidate_return | baseline_return | excess_return |
| --- | --- | --- | --- | --- |
| 0 | 2,022.0000 | 0.2462 | 0.2371 | 0.0091 |
| 1 | 2,023.0000 | 2.7055 | 2.6498 | 0.0557 |
| 2 | 2,024.0000 | 1.0857 | 1.0041 | 0.0816 |
| 3 | 2,025.0000 | 1.9557 | 1.9407 | 0.0150 |
| 4 | 2,026.0000 | 1.5903 | 1.5857 | 0.0046 |

## Rolling-window summary

| index | window | windows | win_rate | worst_excess_multiple | max_mdd_delta |
| --- | --- | --- | --- | --- | --- |
| 0 | 365.0000 | 1,360.0000 | 0.9419 | -0.0077 | 0.0082 |

## Monthly-start summary

| index | starts | win_rate | worst_excess_multiple | max_mdd_delta |
| --- | --- | --- | --- | --- |
| 0 | 54.0000 | 0.9815 | -0.0012 | 0.0049 |

## Decision

**ROBUSTNESS-FAIL (not live approval)**

This audit still cannot close full-history Bitget funding or execution/margin/liquidation
proof. It does not change `PR2026-10-D-L125-V2`.

Research output only; no orders sent.
