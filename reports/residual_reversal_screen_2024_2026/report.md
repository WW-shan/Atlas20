# PIT Top20 residual-reversal screen

- status: factor screen only; no funding; no leverage; no orders
- sample: 2024-01-01 → 2026-09-21
- rebalance events: **36**
- screen verdict: **FAIL**

## Acceptance checks

- [ ] sharpe_20_ge_0_8
- [x] multiple_20_gt_1
- [x] mdd_20_ge_minus_40
- [ ] multiple_50_gt_1
- [ ] sharpe_50_ge_0_5
- [ ] positive_years_ge_80pct
- [ ] both_halves_positive

## Summary

| index | strategy | cost_bps | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | cost_2bps | 2.0000 | 1.3112 | 0.1046 | 0.5255 | -0.3357 |
| 1 | cost_20bps | 20.0000 | 1.1837 | 0.0639 | 0.3734 | -0.3578 |
| 2 | cost_50bps | 50.0000 | 0.9975 | -0.0009 | 0.1200 | -0.4046 |
| 3 | cost_100bps | 100.0000 | 0.7485 | -0.1009 | -0.2932 | -0.4800 |
| 4 | bitcoin_buy_hold | 0.0000 | 1.9608 | 0.2805 | 0.7554 | -0.5306 |

## Yearly returns

| index | year | strategy_20bps | bitcoin |
| --- | --- | --- | --- |
| 0 | 2,024.0000 | 0.5156 | 1.1153 |
| 1 | 2,025.0000 | 0.0244 | -0.0634 |
| 2 | 2,026.0000 | -0.2377 | -0.0104 |

## Largest positive asset contributions at 20bps

| index | asset | cumulative_contribution | absolute_share |
| --- | --- | --- | --- |
| 0 | near | 0.2444 | 0.1101 |
| 1 | stellar | 0.2172 | 0.0978 |
| 2 | solana | 0.1236 | 0.0557 |
| 3 | pepe | 0.1186 | 0.0534 |
| 4 | avalanche-2 | 0.1127 | 0.0507 |
| 5 | ripple | 0.0702 | 0.0316 |
| 6 | mantle | 0.0658 | 0.0296 |
| 7 | chainlink | 0.0622 | 0.0280 |

## Largest negative asset contributions at 20bps

| index | asset | cumulative_contribution | absolute_share |
| --- | --- | --- | --- |
| 0 | hyperliquid | -0.1612 | 0.0726 |
| 1 | bitcoin-cash | -0.1224 | 0.0551 |
| 2 | litecoin | -0.1142 | 0.0514 |
| 3 | cardano | -0.0718 | 0.0323 |
| 4 | uniswap | -0.0650 | 0.0293 |
| 5 | shiba-inu | -0.0600 | 0.0270 |
| 6 | the-open-network | -0.0583 | 0.0262 |
| 7 | dogecoin | -0.0577 | 0.0260 |

## Diagnostics

- turnover at 20bps: **56.7500x**
- max gross at 20bps: **1.0000x**
- missing return observations at 20bps: **0**

## Interpretation guardrail

This screen uses daily panel returns and turnover costs, not Bitget fills, funding, stop-losses or live routing. A pass only earns a follow-up integration study; it is not a live candidate. A fail rejects this frozen configuration, not the broader residual-factor research direction; each new hypothesis must be registered separately.
