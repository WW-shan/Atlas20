# PR2026-11-LS88-LS57-CORE8-LOWFUNDING-LONG

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
| 0 | LS57 baseline | 0.0000 | 20.0000 | two-sided-adverse-3x | 31.4655 | 1.6633 | -0.4376 | 9.9994 | 1.8246 | 1.3326 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | core8 long-only 10% gross | 0.1000 | 20.0000 | two-sided-adverse-3x | 28.1888 | 1.5941 | -0.4409 | 9.6660 | 1.7598 | 1.3999 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 2 | core8 long-only 20% gross | 0.2000 | 20.0000 | two-sided-adverse-3x | 24.5404 | 1.5085 | -0.4415 | 9.1073 | 1.6761 | 1.4279 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 3 | core8 long-only 25% gross | 0.2500 | 20.0000 | two-sided-adverse-3x | 22.6165 | 1.4602 | -0.4556 | 8.8389 | 1.6351 | 1.4391 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 442
- Long observations: 442
- Short observations: 0

## Decision

Baseline/candidate normal 20bps run is incomplete; no promotion inference.

Research output only; not an order or a live approval.
