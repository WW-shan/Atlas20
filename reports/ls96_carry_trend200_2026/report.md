# PR2026-11-LS96-LS82-CARRY-TREND200

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
| 1 | core8 25% residual longMA200 | 0.2500 | 13.0164 | normal | 71.9695 | 1.9974 | -0.3775 | 15.8038 | 2.1442 | 1.4363 | 0.0000 | 0.0000 | 477.0000 | 1.0000 |
| 2 | LS57 baseline | 0.0000 | 20.0000 | normal | 58.2059 | 1.9143 | -0.3983 | 13.8153 | 2.0417 | 1.3306 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 3 | core8 25% residual longMA200 | 0.2500 | 20.0000 | normal | 61.7535 | 1.9349 | -0.3873 | 14.3179 | 2.0772 | 1.4377 | 0.0000 | 0.0000 | 477.0000 | 1.0000 |
| 4 | LS57 baseline | 0.0000 | 50.0000 | normal | 34.6316 | 1.7012 | -0.4344 | 9.9768 | 1.8223 | 1.3342 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 5 | core8 25% residual longMA200 | 0.2500 | 50.0000 | normal | 31.9567 | 1.6653 | -0.4278 | 9.3618 | 1.7882 | 1.4440 | 0.0000 | 0.0000 | 477.0000 | 1.0000 |
| 6 | LS57 baseline | 0.0000 | 100.0000 | normal | 14.5318 | 1.3440 | -0.4942 | 5.7885 | 1.4535 | 1.3403 | 0.0000 | 0.0000 | 247.0000 | 1.0000 |
| 7 | core8 25% residual longMA200 | 0.2500 | 100.0000 | normal | 10.6152 | 1.2134 | -0.5024 | 4.5990 | 1.3025 | 1.4547 | 0.0000 | 0.0000 | 477.0000 | 1.0000 |

## Sleeve selection audit

- Weekly signal dates with at least one selected carry leg: 221
- Total selected leg-observations: 698
- Long observations: 273
- Short observations: 425

## Decision

Best pre-registered 20bps allocation: 25%; full 61.7535x / Sharpe 1.9349 / MDD -38.7341%; validation 14.3179x / Sharpe 2.0772.
Saved reference LS82: 62.1228x / Sharpe 1.9519 / MDD -37.9783%; validation 14.5712x / Sharpe 2.0921.
Pre-registered reference comparison: **FAIL**.

Research output only; not an order or a live approval.
