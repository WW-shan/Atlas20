# PR2026-11-LS85-LS57-ASSET-TREND-200D

- Base: frozen LS57
- New rule: drop a long leg when signal-day close is below its own 200D SMA
- No redistribution; freed weight remains cash; short router unchanged

## Runs

| index | label | cost_bps | funding_scenario | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | max_observed_gross | gross_breach_hours | liquidation_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 baseline | 20.0000 | normal | 58.2059 | 1.9143 | -0.3983 | 13.8153 | 2.0417 | 1.3306 | 0.0000 | 0.0000 |
| 1 | LS85 200D filter | 20.0000 | normal | 30.7807 | 1.7354 | -0.4750 | 11.3117 | 1.9376 | 1.3306 | 0.0000 | 0.0000 |
| 2 | LS57 baseline | 50.0000 | normal | 34.6316 | 1.7012 | -0.4344 | 9.9768 | 1.8223 | 1.3342 | 0.0000 | 0.0000 |
| 3 | LS85 200D filter | 50.0000 | normal | 18.7131 | 1.5170 | -0.5204 | 8.2088 | 1.7162 | 1.3342 | 0.0000 | 0.0000 |
| 4 | LS57 baseline | 100.0000 | normal | 14.5318 | 1.3440 | -0.4942 | 5.7885 | 1.4535 | 1.3403 | 0.0000 | 0.0000 |
| 5 | LS85 200D filter | 100.0000 | normal | 8.1411 | 1.1512 | -0.6043 | 4.8020 | 1.3444 | 1.3403 | 0.0000 | 0.0000 |

## Filter audit

- Events with at least one filtered leg: 68
- Total filtered/cash weight: 22.332068
- Missing-MA leg observations: 35

## Decision

20bps full: base 58.2059x / 1.9143 / -39.8304%; filtered 30.7807x / 1.7354 / -47.5026%.
Primary 20bps gate: **FAIL**.

Research output only; no orders sent.
