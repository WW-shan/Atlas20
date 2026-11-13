# PR2026-11-LS83-CORE8-FUNDING-SETTLEMENT-SCREEN

- Fixed core8 universe; daily 00:00 UTC Binance funding settlement
- Entry at event +1h; exits at +9h and +25h using Bitget market closes
- Long two lowest funding, short two highest; no threshold or lookback scan

## Screen results

| index | sample | horizon_hours | n | gross_mean | net_mean_20bps | net_mean_50bps | net_mean_100bps | cumulative_20bps | max_drawdown_20bps | t_stat | hit_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | full | 8.0000 | 1,666.0000 | 0.0000 | -0.0040 | -0.0100 | -0.0200 | -0.9989 | -0.9989 | 0.0459 | 0.5162 |
| 1 | full | 24.0000 | 1,666.0000 | 0.0005 | -0.0035 | -0.0095 | -0.0195 | -0.9985 | -0.9987 | 0.7622 | 0.5132 |
| 2 | discovery | 8.0000 | 704.0000 | -0.0005 | -0.0045 | -0.0105 | -0.0205 | -0.9617 | -0.9620 | -0.8141 | 0.5114 |
| 3 | discovery | 24.0000 | 704.0000 | 0.0009 | -0.0031 | -0.0091 | -0.0191 | -0.9172 | -0.9383 | 0.8382 | 0.5270 |
| 4 | validation | 8.0000 | 962.0000 | 0.0004 | -0.0036 | -0.0096 | -0.0196 | -0.9712 | -0.9733 | 1.0645 | 0.5198 |
| 5 | validation | 24.0000 | 962.0000 | 0.0002 | -0.0038 | -0.0098 | -0.0198 | -0.9813 | -0.9863 | 0.2362 | 0.5031 |

## Placebo

| index | sample | horizon_hours | actual_mean | placebo_mean | placebo_p95 | placebo_p_value |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | full | 8.0000 | 0.0000 | -0.0000 | 0.0005 | 0.4820 |
| 1 | full | 24.0000 | 0.0005 | -0.0000 | 0.0010 | 0.2145 |
| 2 | discovery | 8.0000 | -0.0005 | -0.0000 | 0.0009 | 0.8095 |
| 3 | discovery | 24.0000 | 0.0009 | -0.0000 | 0.0017 | 0.2005 |
| 4 | validation | 8.0000 | 0.0004 | -0.0000 | 0.0006 | 0.1570 |
| 5 | validation | 24.0000 | 0.0002 | -0.0000 | 0.0013 | 0.3965 |

## Data coverage

- Events retained: 1666
- First event: 2022-01-01 00:00:00+00:00
- Last event: 2026-09-20 00:00:00+00:00

## Decision

8h validation net mean at 50bps: -0.961511%; NW t=1.0645; discovery net mean: -1.049017%.
Screen **FAIL**; do not build a portfolio trial from this event.

Research output only; no orders sent or sanctioned.
