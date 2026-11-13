# PR2026-11-LS84-CORE8-VOLUME-REVERSAL-SCREEN

- Fixed core8 universe; high-volume group = top 4 by 20D volume surprise
- Signal = completed UTC daily return; entry = D+1 03:00 UTC market close
- Long two lowest returns / short two highest returns inside the high-volume group

## Screen results

| index | sample | horizon_hours | n | gross_mean | net_mean_20bps | net_mean_50bps | net_mean_100bps | cumulative_20bps | max_drawdown_20bps | t_stat | hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | full | 24.0000 | 1,644.0000 | -0.0013 | -0.0053 | -0.0113 | -0.0213 | -0.9999 | -0.9999 | -1.8991 | 0.4799 |
| 1 | full | 72.0000 | 1,644.0000 | -0.0022 | -0.0062 | -0.0122 | -0.0222 | -1.0000 | -1.0000 | -1.6985 | 0.4860 |
| 2 | discovery | 24.0000 | 686.0000 | -0.0021 | -0.0061 | -0.0121 | -0.0221 | -0.9885 | -0.9883 | -1.8484 | 0.4708 |
| 3 | discovery | 72.0000 | 686.0000 | -0.0051 | -0.0091 | -0.0151 | -0.0251 | -0.9993 | -0.9993 | -2.3603 | 0.4577 |
| 4 | validation | 24.0000 | 958.0000 | -0.0007 | -0.0047 | -0.0107 | -0.0207 | -0.9924 | -0.9924 | -0.8734 | 0.4864 |
| 5 | validation | 72.0000 | 958.0000 | -0.0000 | -0.0040 | -0.0100 | -0.0200 | -0.9931 | -0.9931 | -0.0241 | 0.5063 |

## Placebo

| index | sample | horizon_hours | actual_mean | placebo_mean | placebo_p95 | placebo_p_value |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | full | 24.0000 | -0.0013 | -0.0000 | 0.0011 | 0.9710 |
| 1 | full | 72.0000 | -0.0022 | 0.0000 | 0.0020 | 0.9640 |
| 2 | discovery | 24.0000 | -0.0021 | 0.0000 | 0.0018 | 0.9700 |
| 3 | discovery | 72.0000 | -0.0051 | 0.0001 | 0.0032 | 0.9960 |
| 4 | validation | 24.0000 | -0.0007 | 0.0000 | 0.0014 | 0.8010 |
| 5 | validation | 72.0000 | -0.0000 | -0.0000 | 0.0025 | 0.5020 |

## Coverage

- Events retained: 1644
- First event: 2022-01-21 00:00:00+00:00
- Last event: 2026-09-17 00:00:00+00:00

## Decision

24h validation net mean at 50bps: -1.074420%; NW t=-0.8734; discovery net mean: -1.205617%.
Screen **FAIL**; do not build a portfolio trial from this event.

Research output only; no orders sent or sanctioned.
