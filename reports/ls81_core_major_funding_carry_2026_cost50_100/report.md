# PR2026-11-LS81-LS57-CORE8-FUNDING-CARRY

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
| 1 | core8 10% residual | 0.1000 | 50.0000 | normal | 33.3424 | 1.6896 | -0.4288 | 9.7800 | 1.8132 | 1.3955 | 0.0000 | 1.0000 | 545.0000 | 1.0000 |
| 2 | core8 20% residual | 0.2000 | 50.0000 | normal | 31.7118 | 1.6706 | -0.4236 | 9.5492 | 1.7991 | 1.5035 | 1.0000 | 1.0000 | 545.0000 | 1.0000 |
| 3 | core8 25% residual | 0.2500 | 50.0000 | normal | 30.8170 | 1.6590 | -0.4209 | 9.4116 | 1.7901 | 1.5163 | 62.0000 | 1.0000 | 545.0000 | 1.0000 |
| 4 | LS57 baseline | 0.0000 | 100.0000 | normal | 14.5318 | 1.3440 | -0.4942 | 5.7885 | 1.4535 | 1.3403 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 5 | core8 10% residual | 0.1000 | 100.0000 | normal | 12.3804 | 1.2809 | -0.4940 | 5.2318 | 1.3877 | 1.4052 | 0.0000 | 1.0000 | 545.0000 | 1.0000 |
| 6 | core8 20% residual | 0.2000 | 100.0000 | normal | 10.4567 | 1.2122 | -0.4942 | 4.7268 | 1.3195 | 1.5145 | 2.0000 | 1.0000 | 545.0000 | 1.0000 |
| 7 | core8 25% residual | 0.2500 | 100.0000 | normal | 9.5522 | 1.1751 | -0.4952 | 4.4731 | 1.2823 | 1.5262 | 63.0000 | 1.0000 | 545.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 884
- Long observations: 442
- Short observations: 442

## Decision

Baseline/candidate normal 20bps run is incomplete; no promotion inference.

Research output only; not an order or a live approval.
