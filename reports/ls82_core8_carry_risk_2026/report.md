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
| 0 | LS57 baseline | 0.0000 | 20.0000 | normal | 58.2059 | 1.9143 | -0.3983 | 13.8153 | 2.0417 | 1.3306 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | core8 25% residual | 0.2500 | 20.0000 | normal | 62.1228 | 1.9519 | -0.3798 | 14.5712 | 2.0921 | 1.4545 | 0.0000 | 0.0000 | 545.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 884
- Long observations: 442
- Short observations: 442

## Decision

Best pre-registered 20bps allocation: 25%; full 62.1228x / Sharpe 1.9519 / MDD -37.9783%; validation 14.5712x / Sharpe 2.0921.
Primary 20bps normal gate: **PASS**.
This is not a live promotion. Cost, adverse-funding, rolling, bootstrap and independent OOS checks remain required.

Research output only; not an order or a live approval.
