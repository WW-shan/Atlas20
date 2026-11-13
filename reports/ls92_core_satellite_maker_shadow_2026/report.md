# PR2026-11-LS92-LS91-MAKER25-SHADOW

- Capital weights: 50.0% LS57 + 25.0% LS82_CARRY + 25.0% LS88_LONG_CARRY + 0.0% LS89_MA21
- Cost assumption: 13.0164bps per side, using the matching saved engine returns
- No cross-account rebalancing; each subaccount compounds independently

## Portfolio results

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 13.0164 | 65.6712 | 1.9638 | -0.3896 | 14.9011 | 2.0925 |
| 1 | LS82_CARRY | 13.0164 | 73.0767 | 2.0189 | -0.3700 | 16.1532 | 2.1621 |
| 2 | LS88_LONG_CARRY | 13.0164 | 70.4673 | 1.9610 | -0.3851 | 15.6631 | 2.0743 |
| 3 | LS89_MA21 | 13.0164 | 61.7783 | 1.9785 | -0.3559 | 13.1031 | 2.0631 |
| 4 | PR2026-11-LS92-LS91-MAKER25-SHADOW | 13.0164 | 68.7216 | 1.9797 | -0.3837 | 15.4108 | 2.1078 |

## Subaccounts (13.0164bps)

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 13.0164 | 65.6712 | 1.9638 | -0.3896 | 14.9011 | 2.0925 |
| 1 | LS82_CARRY | 13.0164 | 73.0767 | 2.0189 | -0.3700 | 16.1532 | 2.1621 |
| 2 | LS88_LONG_CARRY | 13.0164 | 70.4673 | 1.9610 | -0.3851 | 15.6631 | 2.0743 |
| 3 | LS89_MA21 | 13.0164 | 61.7783 | 1.9785 | -0.3559 | 13.1031 | 2.0631 |

## Return correlations (13.0164bps)

| index | index | LS57 | LS82_CARRY | LS88_LONG_CARRY | LS89_MA21 |
| --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 1.0000 | 0.9953 | 0.9934 | 0.9835 |
| 1 | LS82_CARRY | 0.9953 | 1.0000 | 0.9912 | 0.9785 |
| 2 | LS88_LONG_CARRY | 0.9934 | 0.9912 | 1.0000 | 0.9741 |
| 3 | LS89_MA21 | 0.9835 | 0.9785 | 0.9741 | 1.0000 |

## Decision

13.0164bps LS57: 65.6712x / 1.9638 / -38.9592%; PR2026-11-LS92-LS91-MAKER25-SHADOW: 68.7216x / 1.9797 / -38.3694%.
Primary ensemble gate: **PASS**.
This is a portfolio candidate only; no live promotion.

Research output only; no orders sent.
