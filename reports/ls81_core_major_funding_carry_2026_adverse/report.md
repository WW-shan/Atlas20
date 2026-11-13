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
| 0 | LS57 baseline | 0.0000 | 20.0000 | two-sided-adverse-1x | 50.1759 | 1.8533 | -0.4123 | 13.0562 | 2.0036 | 1.3314 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | core8 10% residual | 0.1000 | 20.0000 | two-sided-adverse-1x | 48.7861 | 1.8460 | -0.4066 | 13.0075 | 2.0059 | 1.3943 | 0.0000 | 1.0000 | 545.0000 | 1.0000 |
| 2 | core8 20% residual | 0.2000 | 20.0000 | two-sided-adverse-1x | 46.7593 | 1.8304 | -0.4009 | 12.8781 | 2.0019 | 1.4979 | 0.0000 | 1.0000 | 545.0000 | 1.0000 |
| 3 | core8 25% residual | 0.2500 | 20.0000 | two-sided-adverse-1x | 45.6780 | 1.8210 | -0.3985 | 12.7947 | 1.9985 | 1.5163 | 60.0000 | 1.0000 | 545.0000 | 1.0000 |
| 4 | LS57 baseline | 0.0000 | 20.0000 | two-sided-adverse-3x | 31.4655 | 1.6633 | -0.4376 | 9.9994 | 1.8246 | 1.3326 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 5 | core8 10% residual | 0.1000 | 20.0000 | two-sided-adverse-3x | 27.7030 | 1.6144 | -0.4355 | 9.4804 | 1.7929 | 1.3956 | 0.0000 | 1.0000 | 545.0000 | 1.0000 |
| 6 | core8 20% residual | 0.2000 | 20.0000 | two-sided-adverse-3x | 24.0513 | 1.5575 | -0.4337 | 8.9332 | 1.7548 | 1.4999 | 0.0000 | 1.0000 | 545.0000 | 1.0000 |
| 7 | core8 25% residual | 0.2500 | 20.0000 | two-sided-adverse-3x | 22.3633 | 1.5275 | -0.4332 | 8.6590 | 1.7344 | 1.5163 | 63.0000 | 1.0000 | 545.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 884
- Long observations: 442
- Short observations: 442

## Decision

Baseline/candidate normal 20bps run is incomplete; no promotion inference.

Research output only; not an order or a live approval.
