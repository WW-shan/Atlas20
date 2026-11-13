# PR2026-11-LS92-LS91-MAKER25-SHADOW

- Equal initial capital: 25% to each real-engine subaccount
- No cross-account rebalancing; each subaccount compounds independently
- 20bps is primary; 50/100bps use their corresponding saved engine returns

## Portfolio results

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 13.0164 | 65.6712 | 1.9638 | -0.3896 | 14.9011 | 2.0925 |
| 1 | LS82_CARRY | 13.0164 | 73.0767 | 2.0189 | -0.3700 | 16.1532 | 2.1621 |
| 2 | LS88_LONG_CARRY | 13.0164 | 70.4673 | 1.9610 | -0.3851 | 15.6631 | 2.0743 |
| 3 | LS89_MA21 | 13.0164 | 61.7783 | 1.9785 | -0.3559 | 13.1031 | 2.0631 |
| 4 | PR2026-11-LS92-LS91-MAKER25-SHADOW | 13.0164 | 68.7216 | 1.9797 | -0.3837 | 15.4108 | 2.1078 |

## Subaccounts (20bps)

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 13.0164 | 65.6712 | 1.9638 | -0.3896 | 14.9011 | 2.0925 |
| 1 | LS82_CARRY | 13.0164 | 73.0767 | 2.0189 | -0.3700 | 16.1532 | 2.1621 |
| 2 | LS88_LONG_CARRY | 13.0164 | 70.4673 | 1.9610 | -0.3851 | 15.6631 | 2.0743 |
| 3 | LS89_MA21 | 13.0164 | 61.7783 | 1.9785 | -0.3559 | 13.1031 | 2.0631 |

## Return correlations (20bps)

| index | index | LS57 | LS82_CARRY | LS88_LONG_CARRY | LS89_MA21 |
| --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 1.0000 | 0.9953 | 0.9934 | 0.9835 |
| 1 | LS82_CARRY | 0.9953 | 1.0000 | 0.9912 | 0.9785 |
| 2 | LS88_LONG_CARRY | 0.9934 | 0.9912 | 1.0000 | 0.9741 |
| 3 | LS89_MA21 | 0.9835 | 0.9785 | 0.9741 | 1.0000 |

## Decision

20bps portfolio comparison is incomplete.

Research output only; no orders sent.
