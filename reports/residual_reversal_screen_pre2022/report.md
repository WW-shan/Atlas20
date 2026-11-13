# PIT Top20 residual-reversal screen

- status: factor screen only; no funding; no leverage; no orders
- sample: 2020-09-03 → 2021-12-31
- rebalance events: **14**
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
| 0 | cost_2bps | 2.0000 | 0.6920 | -0.2425 | -0.4510 | -0.4828 |
| 1 | cost_20bps | 20.0000 | 0.6632 | -0.2663 | -0.5237 | -0.4978 |
| 2 | cost_50bps | 50.0000 | 0.6177 | -0.3046 | -0.6429 | -0.5220 |
| 3 | cost_100bps | 100.0000 | 0.5483 | -0.3644 | -0.8354 | -0.5601 |
| 4 | bitcoin_buy_hold | 0.0000 | 4.5198 | 2.1192 | 1.8913 | -0.5306 |

## Yearly returns

| index | year | strategy_20bps | bitcoin |
| --- | --- | --- | --- |
| 0 | 2,020.0000 | -0.1709 | 1.8307 |
| 1 | 2,021.0000 | -0.2001 | 0.5967 |

## Largest positive asset contributions at 20bps

| index | asset | cumulative_contribution | absolute_share |
| --- | --- | --- | --- |
| 0 | stellar | 0.1428 | 0.0673 |
| 1 | eos | 0.1150 | 0.0541 |
| 2 | ripple | 0.1146 | 0.0539 |
| 3 | monero | 0.1089 | 0.0513 |
| 4 | matic-network | 0.0710 | 0.0334 |
| 5 | bitcoin-cash | 0.0664 | 0.0312 |
| 6 | elrond-erd-2 | 0.0592 | 0.0279 |
| 7 | shiba-inu | 0.0550 | 0.0259 |

## Largest negative asset contributions at 20bps

| index | asset | cumulative_contribution | absolute_share |
| --- | --- | --- | --- |
| 0 | uniswap | -0.2518 | 0.1186 |
| 1 | terra-luna | -0.1611 | 0.0758 |
| 2 | polkadot | -0.1415 | 0.0666 |
| 3 | aave | -0.1248 | 0.0588 |
| 4 | binancecoin | -0.1104 | 0.0520 |
| 5 | filecoin | -0.1034 | 0.0487 |
| 6 | cardano | -0.0915 | 0.0431 |
| 7 | ethereum | -0.0459 | 0.0216 |

## Diagnostics

- turnover at 20bps: **23.0000x**
- max gross at 20bps: **1.0000x**
- missing return observations at 20bps: **0**

## Interpretation guardrail

This screen uses daily panel returns and turnover costs, not Bitget fills, funding, stop-losses or live routing. A pass only earns a follow-up integration study; it is not a live candidate. A fail rejects this frozen configuration, not the broader residual-factor research direction; each new hypothesis must be registered separately.
