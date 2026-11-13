# PR2026-11-LS81-LS57-CORE8-FUNDING-CARRY

- Window: 2022-01-01 → 2026-09-21 (UTC)
- Core universe: bitcoin, ethereum, solana, ripple, binancecoin, dogecoin, cardano, avalanche-2, chainlink, polkadot
- Bitget mark symbols: 88; Bitget market symbols: 88
- Base: frozen LS57; only residual gross is used by the carry sleeve
- Signal: Binance 8h funding settlements strictly before D; D settlement excluded
- Execution: T+1 UTC +3h; Bitget mark for mark/liquidation; Bitget market for fills
- This is research-only; no orders are routed

## Runs

| index | label | allocation | cost_bps | funding_scenario | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | max_observed_gross | gross_breach_hours | liquidation_count | mark_carry_count | mark_carry_max_hours |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 baseline | 0.0000 | 20.0000 | normal | 58.2059 | 1.9143 | -0.3983 | 13.8153 | 2.0417 | 1.3306 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 1 | extended10 10% residual | 0.1000 | 20.0000 | normal | 58.0311 | 1.9191 | -0.3998 | 14.2244 | 2.0671 | 1.4365 | 0.0000 | 1.0000 | 561.0000 | 1.0000 |
| 2 | extended10 20% residual | 0.2000 | 20.0000 | normal | 56.9244 | 1.9148 | -0.4009 | 14.5042 | 2.0837 | 1.5171 | 10.0000 | 1.0000 | 561.0000 | 1.0000 |
| 3 | extended10 25% residual | 0.2500 | 20.0000 | normal | 57.4495 | 1.9189 | -0.4021 | 14.6739 | 2.0924 | 1.5171 | 64.0000 | 1.0000 | 561.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 246
- Total selected leg-observations: 984
- Long observations: 492
- Short observations: 492

## Decision

Best pre-registered 20bps allocation: 10%; full 58.0311x / Sharpe 1.9191 / MDD -39.9792%; validation 14.2244x / Sharpe 2.0671.
Primary 20bps normal gate: **FAIL**.

Research output only; not an order or a live approval.
