# PR2026-11-LS89-LS57-ASSET-MA21-EXIT

- Base: frozen LS57
- New rule: drop a long leg when signal-day close is below its own 21D SMA
- No redistribution; freed weight remains cash; short router unchanged

## Runs

| index | label | cost_bps | funding_scenario | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | max_observed_gross | gross_breach_hours | liquidation_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 baseline | 20.0000 | normal | 58.2059 | 1.9143 | -0.3983 | 13.8153 | 2.0417 | 1.3306 | 0.0000 | 0.0000 |
| 1 | PR2026-11-LS89-LS57-ASSET-MA21-EXIT 21D filter | 20.0000 | normal | 54.7231 | 1.9275 | -0.3648 | 12.1321 | 2.0093 | 1.3306 | 0.0000 | 0.0000 |
| 2 | LS57 baseline | 50.0000 | normal | 34.6316 | 1.7012 | -0.4344 | 9.9768 | 1.8223 | 1.3342 | 0.0000 | 0.0000 |
| 3 | PR2026-11-LS89-LS57-ASSET-MA21-EXIT 21D filter | 50.0000 | normal | 32.4785 | 1.7075 | -0.4016 | 8.7115 | 1.7771 | 1.3342 | 0.0000 | 0.0000 |
| 4 | LS57 baseline | 100.0000 | normal | 14.5318 | 1.3440 | -0.4942 | 5.7885 | 1.4535 | 1.3403 | 0.0000 | 0.0000 |
| 5 | PR2026-11-LS89-LS57-ASSET-MA21-EXIT 21D filter | 100.0000 | normal | 13.5751 | 1.3386 | -0.4735 | 5.0071 | 1.3868 | 1.3403 | 0.0000 | 0.0000 |

## Filter audit

- Events with at least one filtered leg: 147
- Total filtered/cash weight: 36.472873
- Missing-MA leg observations: 0

## Decision

20bps full: base 58.2059x / 1.9143 / -39.8304%; filtered 54.7231x / 1.9275 / -36.4793%.
Primary 20bps gate: **FAIL**.

Research output only; no orders sent.
