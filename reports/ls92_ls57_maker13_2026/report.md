# PR2026-11-LS92-LS57-MAKER13-BASE

- Base: frozen LS57
- New rule: drop a long leg when signal-day close is below its own 21D SMA
- No redistribution; freed weight remains cash; short router unchanged

## Runs

| index | label | cost_bps | funding_scenario | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | max_observed_gross | gross_breach_hours | liquidation_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 baseline | 13.0164 | normal | 65.6712 | 1.9638 | -0.3896 | 14.9011 | 2.0925 | 1.3297 | 0.0000 | 0.0000 |
| 1 | PR2026-11-LS92-LS57-MAKER13-BASE 21D filter | 13.0164 | normal | 61.7783 | 1.9785 | -0.3559 | 13.1031 | 2.0631 | 1.3297 | 0.0000 | 0.0000 |

## Filter audit

- Events with at least one filtered leg: 147
- Total filtered/cash weight: 36.472873
- Missing-MA leg observations: 0

## Decision

Normal 20bps baseline/filtered run is incomplete.

Research output only; no orders sent.
