# PR2026-11-LS87-PIT-TOP20-REALIZED-SKEW-SCREEN

- PIT CMC Top20 membership; Bitget market candle required for execution
- 30D daily-return realized skew; long two lowest, short two highest
- Weekly 7D hold; entry D+1 03:00 UTC; exit +7D

## Screen results

| index | sample | horizon_days | n | gross_mean | net_mean_20bps | net_mean_50bps | net_mean_100bps | cumulative_20bps | max_drawdown_20bps | t_stat | hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | full | 7.0000 | 241.0000 | -0.0047 | -0.0087 | -0.0147 | -0.0247 | -0.9845 | -0.9909 | -0.6954 | 0.5353 |
| 1 | discovery | 7.0000 | 102.0000 | -0.0118 | -0.0158 | -0.0218 | -0.0318 | -0.9052 | -0.9296 | -1.1483 | 0.4706 |
| 2 | validation | 7.0000 | 139.0000 | 0.0005 | -0.0035 | -0.0095 | -0.0195 | -0.8366 | -0.8964 | 0.0554 | 0.5827 |

## Placebo

| index | sample | actual_mean | placebo_mean | placebo_p95 | placebo_p_value |
| --- | --- | --- | --- | --- | --- |
| 0 | full | -0.0047 | -0.0001 | 0.0089 | 0.8095 |
| 1 | discovery | -0.0118 | -0.0001 | 0.0124 | 0.9380 |
| 2 | validation | 0.0005 | -0.0000 | 0.0123 | 0.4715 |

## Coverage

- Events: 241
- Median eligible assets: 19.0

## Decision

Validation 7D net mean at 50bps: -0.949962%; NW t=0.0554; discovery net mean: -2.181530%.
Screen **FAIL**; do not build a portfolio trial from this event.

Research output only; no orders sent or sanctioned.
