# PR2026-11-LS89-LS57-ASSET-MA21-EXIT

- Base: frozen LS57
- New rule: drop a long leg when signal-day close is below its own 21D SMA
- No redistribution; freed weight remains cash; short router unchanged

## Runs

| index | label | cost_bps | funding_scenario | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | max_observed_gross | gross_breach_hours | liquidation_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 baseline | 20.0000 | two-sided-adverse-3x | 31.4655 | 1.6633 | -0.4376 | 9.9994 | 1.8246 | 1.3326 | 0.0000 | 0.0000 |
| 1 | PR2026-11-LS89-LS57-ASSET-MA21-EXIT 21D filter | 20.0000 | two-sided-adverse-3x | 30.8057 | 1.6868 | -0.4024 | 9.0084 | 1.8020 | 1.3326 | 0.0000 | 0.0000 |

## Filter audit

- Events with at least one filtered leg: 147
- Total filtered/cash weight: 36.472873
- Missing-MA leg observations: 0

## Decision

Normal 20bps baseline/filtered run is incomplete.

Research output only; no orders sent.
