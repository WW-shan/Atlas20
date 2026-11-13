# PR2026-11-LS85-LS57-ASSET-TREND-200D

- Base: frozen LS57
- New rule: drop a long leg when signal-day close is below its own 200D SMA
- No redistribution; freed weight remains cash; short router unchanged

## Runs

| index | label | cost_bps | funding_scenario | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | max_observed_gross | gross_breach_hours | liquidation_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 baseline | 20.0000 | two-sided-adverse-3x | 31.4655 | 1.6633 | -0.4376 | 9.9994 | 1.8246 | 1.3326 | 0.0000 | 0.0000 |
| 1 | LS85 200D filter | 20.0000 | two-sided-adverse-3x | 17.0906 | 1.4785 | -0.5363 | 8.2669 | 1.7220 | 1.3326 | 0.0000 | 0.0000 |

## Filter audit

- Events with at least one filtered leg: 68
- Total filtered/cash weight: 22.332068
- Missing-MA leg observations: 35

## Decision

Normal 20bps baseline/filtered run is incomplete.

Research output only; no orders sent.
