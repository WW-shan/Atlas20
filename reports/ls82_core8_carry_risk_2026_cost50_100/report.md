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
| 0 | LS57 baseline | 0.0000 | 50.0000 | normal | 34.6316 | 1.7012 | -0.4344 | 9.9768 | 1.8223 | 1.3342 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | core8 25% residual | 0.2500 | 50.0000 | normal | 30.8855 | 1.6629 | -0.4203 | 9.3515 | 1.7896 | 1.4561 | 0.0000 | 0.0000 | 545.0000 | 1.0000 |
| 2 | LS57 baseline | 0.0000 | 100.0000 | normal | 14.5318 | 1.3440 | -0.4942 | 5.7885 | 1.4535 | 1.3403 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 3 | core8 25% residual | 0.2500 | 100.0000 | normal | 9.5926 | 1.1784 | -0.4950 | 4.4527 | 1.2814 | 1.4587 | 0.0000 | 0.0000 | 545.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 884
- Long observations: 442
- Short observations: 442

## Decision

Baseline/candidate normal 20bps run is incomplete; no promotion inference.

Research output only; not an order or a live approval.
