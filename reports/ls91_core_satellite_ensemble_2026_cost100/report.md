# PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE

- Capital weights: 50.0% LS57 + 25.0% LS82_CARRY + 25.0% LS88_LONG_CARRY + 0.0% LS89_MA21
- Cost assumption: 100bps per side, using the matching saved engine returns
- No cross-account rebalancing; each subaccount compounds independently

## Portfolio results

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 100.0000 | 14.5318 | 1.3440 | -0.4942 | 5.7885 | 1.4535 |
| 1 | LS82_CARRY | 100.0000 | 9.5926 | 1.1784 | -0.4950 | 4.4527 | 1.2814 |
| 2 | LS88_LONG_CARRY | 100.0000 | 12.7656 | 1.2740 | -0.4956 | 5.3701 | 1.3737 |
| 3 | LS89_MA21 | 100.0000 | 13.5751 | 1.3386 | -0.4735 | 5.0071 | 1.3868 |
| 4 | PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE | 100.0000 | 12.8555 | 1.2920 | -0.4941 | 5.3831 | 1.3994 |

## Subaccounts (100bps)

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 100.0000 | 14.5318 | 1.3440 | -0.4942 | 5.7885 | 1.4535 |
| 1 | LS82_CARRY | 100.0000 | 9.5926 | 1.1784 | -0.4950 | 4.4527 | 1.2814 |
| 2 | LS88_LONG_CARRY | 100.0000 | 12.7656 | 1.2740 | -0.4956 | 5.3701 | 1.3737 |
| 3 | LS89_MA21 | 100.0000 | 13.5751 | 1.3386 | -0.4735 | 5.0071 | 1.3868 |

## Return correlations (100bps)

| index | index | LS57 | LS82_CARRY | LS88_LONG_CARRY | LS89_MA21 |
| --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 1.0000 | 0.9947 | 0.9933 | 0.9832 |
| 1 | LS82_CARRY | 0.9947 | 1.0000 | 0.9907 | 0.9774 |
| 2 | LS88_LONG_CARRY | 0.9933 | 0.9907 | 1.0000 | 0.9738 |
| 3 | LS89_MA21 | 0.9832 | 0.9774 | 0.9738 | 1.0000 |

## Decision

100bps LS57: 14.5318x / 1.3440 / -49.4222%; PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE: 12.8555x / 1.2920 / -49.4134%.
Primary ensemble gate: **FAIL**.

Research output only; no orders sent.
