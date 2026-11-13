# PR2026-11-LS92-LS88-MAKER13

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
| 0 | LS57 baseline | 0.0000 | 13.0164 | normal | 65.6712 | 1.9638 | -0.3896 | 14.9011 | 2.0925 | 1.3297 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | core8 long-only 10% gross | 0.1000 | 13.0164 | normal | 70.4673 | 1.9610 | -0.3851 | 15.6631 | 2.0743 | 1.3984 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 442
- Long observations: 442
- Short observations: 0

## Decision

Baseline/candidate normal 20bps run is incomplete; no promotion inference.

Research output only; not an order or a live approval.
