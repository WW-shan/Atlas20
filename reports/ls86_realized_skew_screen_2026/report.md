# PR2026-11-LS86-CORE8-REALIZED-SKEW-SCREEN

- Fixed core8; 30D daily-return realized skewness
- Long two lowest skew / short two highest skew; weekly 7D hold
- Entry at D+1 03:00 UTC; exit at +7D using Bitget market closes

## Screen results

| index | sample | horizon_days | n | gross_mean | net_mean_20bps | net_mean_50bps | net_mean_100bps | cumulative_20bps | max_drawdown_20bps | t_stat | hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | full | 7.0000 | 235.0000 | -0.0015 | -0.0055 | -0.0115 | -0.0215 | -0.9323 | -0.9621 | -0.2642 | 0.5106 |
| 1 | discovery | 7.0000 | 98.0000 | -0.0018 | -0.0058 | -0.0118 | -0.0218 | -0.6486 | -0.8302 | -0.2044 | 0.5000 |
| 2 | validation | 7.0000 | 137.0000 | -0.0013 | -0.0053 | -0.0113 | -0.0213 | -0.8073 | -0.8980 | -0.1736 | 0.5182 |

## Placebo

| index | sample | actual_mean | placebo_mean | placebo_p95 | placebo_p_value |
| --- | --- | --- | --- | --- | --- |
| 0 | full | -0.0015 | -0.0001 | 0.0086 | 0.6040 |
| 1 | discovery | -0.0018 | 0.0000 | 0.0135 | 0.5815 |
| 2 | validation | -0.0013 | 0.0001 | 0.0113 | 0.5795 |

## Decision

Validation 7D net mean at 50bps: -1.131002%; NW t=-0.1736; discovery net mean: -1.180214%.
Screen **FAIL**; do not build a portfolio trial from this event.

Research output only; no orders sent or sanctioned.
