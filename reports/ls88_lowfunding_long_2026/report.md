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
| 0 | LS57 baseline | 0.0000 | 20.0000 | normal | 58.2059 | 1.9143 | -0.3983 | 13.8153 | 2.0417 | 1.3306 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | core8 long-only 10% gross | 0.1000 | 20.0000 | normal | 61.4661 | 1.9062 | -0.3941 | 14.3776 | 2.0185 | 1.3987 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 2 | core8 long-only 20% gross | 0.2000 | 20.0000 | normal | 63.0370 | 1.8759 | -0.3865 | 14.5795 | 1.9717 | 1.4255 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 3 | core8 long-only 25% gross | 0.2500 | 20.0000 | normal | 63.0364 | 1.8528 | -0.3849 | 14.6717 | 1.9474 | 1.4360 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 442
- Long observations: 442
- Short observations: 0

## Decision

Best pre-registered 20bps allocation: 20%; full 63.0370x / Sharpe 1.8759 / MDD -38.6514%; validation 14.5795x / Sharpe 1.9717.
Primary 20bps normal gate: **FAIL**.

Research output only; not an order or a live approval.
