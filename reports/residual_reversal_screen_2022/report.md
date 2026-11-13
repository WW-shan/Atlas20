# PIT Top20 residual-reversal screen

- status: factor screen only; no funding; no leverage; no orders
- sample: 2022-01-01 → 2026-09-21
- rebalance events: **62**
- screen verdict: **FAIL**

## Acceptance checks

- [ ] sharpe_20_ge_0_8
- [ ] multiple_20_gt_1
- [ ] mdd_20_ge_minus_40
- [ ] multiple_50_gt_1
- [ ] sharpe_50_ge_0_5
- [ ] positive_years_ge_80pct
- [ ] both_halves_positive

## Summary

| index | strategy | cost_bps | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | cost_2bps | 2.0000 | 0.8893 | -0.0245 | 0.1138 | -0.5930 |
| 1 | cost_20bps | 20.0000 | 0.7463 | -0.0601 | 0.0012 | -0.6166 |
| 2 | cost_50bps | 50.0000 | 0.5565 | -0.1167 | -0.1852 | -0.6791 |
| 3 | cost_100bps | 100.0000 | 0.3401 | -0.2041 | -0.4894 | -0.7963 |
| 4 | bitcoin_buy_hold | 0.0000 | 1.8161 | 0.1347 | 0.5026 | -0.6689 |

## Yearly returns

| index | year | strategy_20bps | bitcoin |
| --- | --- | --- | --- |
| 0 | 2,022.0000 | -0.1775 | -0.6530 |
| 1 | 2,023.0000 | -0.1716 | 1.5542 |
| 2 | 2,024.0000 | 0.3451 | 1.2105 |
| 3 | 2,025.0000 | -0.1883 | -0.0634 |
| 4 | 2,026.0000 | 0.0032 | -0.0104 |

## Largest positive asset contributions at 20bps

| index | asset | cumulative_contribution | absolute_share |
| --- | --- | --- | --- |
| 0 | near | 0.2833 | 0.0888 |
| 1 | terra-luna | 0.2484 | 0.0778 |
| 2 | stellar | 0.2459 | 0.0771 |
| 3 | binancecoin | 0.1262 | 0.0396 |
| 4 | pepe | 0.1117 | 0.0350 |
| 5 | cardano | 0.0792 | 0.0248 |
| 6 | polkadot | 0.0790 | 0.0248 |
| 7 | litecoin | 0.0673 | 0.0211 |

## Largest negative asset contributions at 20bps

| index | asset | cumulative_contribution | absolute_share |
| --- | --- | --- | --- |
| 0 | ftx-token | -0.2616 | 0.0820 |
| 1 | bitcoin-cash | -0.2414 | 0.0756 |
| 2 | cosmos | -0.2137 | 0.0670 |
| 3 | tron | -0.1514 | 0.0474 |
| 4 | zcash | -0.1273 | 0.0399 |
| 5 | ripple | -0.1240 | 0.0389 |
| 6 | the-open-network | -0.0740 | 0.0232 |
| 7 | monero | -0.0723 | 0.0226 |

## Diagnostics

- turnover at 20bps: **97.0000x**
- max gross at 20bps: **1.0000x**
- missing return observations at 20bps: **1**

## Interpretation guardrail

This screen uses daily panel returns and turnover costs, not Bitget fills, funding, stop-losses or live routing. A pass only earns a follow-up integration study; it is not a live candidate. A fail rejects this frozen configuration, not the broader residual-factor research direction; each new hypothesis must be registered separately.
