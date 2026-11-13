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
| 0 | LS57 baseline | 0.0000 | 50.0000 | normal | 34.6316 | 1.7012 | -0.4344 | 9.9768 | 1.8223 | 1.3342 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | core8 long-only 10% gross | 0.1000 | 50.0000 | normal | 34.1389 | 1.6700 | -0.4311 | 9.9461 | 1.7779 | 1.3999 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 2 | core8 long-only 20% gross | 0.2000 | 50.0000 | normal | 32.7778 | 1.6208 | -0.4245 | 9.6805 | 1.7141 | 1.4315 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 3 | core8 long-only 25% gross | 0.2500 | 50.0000 | normal | 31.6504 | 1.5885 | -0.4240 | 9.5366 | 1.6816 | 1.4378 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 4 | LS57 baseline | 0.0000 | 100.0000 | normal | 14.5318 | 1.3440 | -0.4942 | 5.7885 | 1.4535 | 1.3403 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 5 | core8 long-only 10% gross | 0.1000 | 100.0000 | normal | 12.7656 | 1.2740 | -0.4956 | 5.3701 | 1.3737 | 1.4083 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 6 | core8 long-only 20% gross | 0.2000 | 100.0000 | normal | 10.9744 | 1.1930 | -0.5033 | 4.8792 | 1.2814 | 1.4416 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |
| 7 | core8 long-only 25% gross | 0.2500 | 100.0000 | normal | 9.9925 | 1.1456 | -0.5258 | 4.6380 | 1.2355 | 1.4513 | 0.0000 | 0.0000 | 398.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 442
- Long observations: 442
- Short observations: 0

## Decision

Baseline/candidate normal 20bps run is incomplete; no promotion inference.

Research output only; not an order or a live approval.
