# PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE

- Capital weights: 50.0% LS57 + 25.0% LS82_CARRY + 25.0% LS88_LONG_CARRY + 0.0% LS89_MA21
- Cost assumption: 20bps per side, using the matching saved engine returns
- No cross-account rebalancing; each subaccount compounds independently

## Portfolio results

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 20.0000 | 58.2059 | 1.9143 | -0.3983 | 13.8153 | 2.0417 |
| 1 | LS82_CARRY | 20.0000 | 62.1228 | 1.9519 | -0.3798 | 14.5712 | 2.0921 |
| 2 | LS88_LONG_CARRY | 20.0000 | 61.4661 | 1.9062 | -0.3941 | 14.3776 | 2.0185 |
| 3 | LS89_MA21 | 20.0000 | 54.7231 | 1.9275 | -0.3648 | 12.1321 | 2.0093 |
| 4 | PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE | 20.0000 | 60.0002 | 1.9242 | -0.3928 | 14.1470 | 2.0505 |

## Subaccounts (20bps)

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 20.0000 | 58.2059 | 1.9143 | -0.3983 | 13.8153 | 2.0417 |
| 1 | LS82_CARRY | 20.0000 | 62.1228 | 1.9519 | -0.3798 | 14.5712 | 2.0921 |
| 2 | LS88_LONG_CARRY | 20.0000 | 61.4661 | 1.9062 | -0.3941 | 14.3776 | 2.0185 |
| 3 | LS89_MA21 | 20.0000 | 54.7231 | 1.9275 | -0.3648 | 12.1321 | 2.0093 |

## Return correlations (20bps)

| index | index | LS57 | LS82_CARRY | LS88_LONG_CARRY | LS89_MA21 |
| --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 1.0000 | 0.9953 | 0.9934 | 0.9835 |
| 1 | LS82_CARRY | 0.9953 | 1.0000 | 0.9911 | 0.9784 |
| 2 | LS88_LONG_CARRY | 0.9934 | 0.9911 | 1.0000 | 0.9741 |
| 3 | LS89_MA21 | 0.9835 | 0.9784 | 0.9741 | 1.0000 |

## Decision

20bps LS57: 58.2059x / 1.9143 / -39.8304%; PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE: 60.0002x / 1.9242 / -39.2754%.
Primary ensemble gate: **PASS**.
This is a portfolio candidate only; no live promotion.

Research output only; no orders sent.
