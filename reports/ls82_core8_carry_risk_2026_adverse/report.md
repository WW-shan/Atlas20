# PR2026-11-LS82-LS57-CORE8-CARRY-RISK

- Window: 2022-01-01 → 2026-09-21 (UTC)
- Core universe: bitcoin, ethereum, solana, ripple, binancecoin, dogecoin, cardano, avalanche-2
- Bitget mark symbols: 88; Bitget market symbols: 88
- Base: frozen LS57; only residual gross is used by the carry sleeve
- Signal: Binance 8h funding settlements strictly before D; D settlement excluded
- Execution: T+1 UTC +3h; Bitget mark for mark/liquidation; Bitget market for fills
- This is research-only; no orders are routed

## Runs

| index | label | allocation | cost_bps | funding_scenario | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | max_observed_gross | gross_breach_hours | liquidation_count | mark_carry_count | mark_carry_max_hours |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 baseline | 0.0000 | 20.0000 | two-sided-adverse-1x | 50.1759 | 1.8533 | -0.4123 | 13.0562 | 2.0036 | 1.3314 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | core8 25% residual | 0.2500 | 20.0000 | two-sided-adverse-1x | 45.7220 | 1.8250 | -0.3975 | 12.7027 | 1.9983 | 1.4546 | 0.0000 | 0.0000 | 545.0000 | 1.0000 |
| 2 | LS57 baseline | 0.0000 | 20.0000 | two-sided-adverse-3x | 31.4655 | 1.6633 | -0.4376 | 9.9994 | 1.8246 | 1.3326 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 3 | core8 25% residual | 0.2500 | 20.0000 | two-sided-adverse-3x | 22.3991 | 1.5309 | -0.4322 | 8.6047 | 1.7339 | 1.4552 | 0.0000 | 0.0000 | 545.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 884
- Long observations: 442
- Short observations: 442

## Decision

Baseline/candidate normal 20bps run is incomplete; no promotion inference.

Research output only; not an order or a live approval.
