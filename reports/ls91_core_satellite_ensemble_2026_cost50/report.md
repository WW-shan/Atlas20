# PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE

- Capital weights: 50.0% LS57 + 25.0% LS82_CARRY + 25.0% LS88_LONG_CARRY + 0.0% LS89_MA21
- Cost assumption: 50bps per side, using the matching saved engine returns
- No cross-account rebalancing; each subaccount compounds independently

## Portfolio results

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 50.0000 | 34.6316 | 1.7012 | -0.4344 | 9.9768 | 1.8223 |
| 1 | LS82_CARRY | 50.0000 | 30.8855 | 1.6629 | -0.4203 | 9.3515 | 1.7896 |
| 2 | LS88_LONG_CARRY | 50.0000 | 34.1389 | 1.6700 | -0.4311 | 9.9461 | 1.7779 |
| 3 | LS89_MA21 | 50.0000 | 32.4785 | 1.7075 | -0.4016 | 8.7115 | 1.7771 |
| 4 | PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE | 50.0000 | 33.5719 | 1.6862 | -0.4302 | 9.8181 | 1.8050 |

## Subaccounts (50bps)

| index | portfolio | cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 50.0000 | 34.6316 | 1.7012 | -0.4344 | 9.9768 | 1.8223 |
| 1 | LS82_CARRY | 50.0000 | 30.8855 | 1.6629 | -0.4203 | 9.3515 | 1.7896 |
| 2 | LS88_LONG_CARRY | 50.0000 | 34.1389 | 1.6700 | -0.4311 | 9.9461 | 1.7779 |
| 3 | LS89_MA21 | 50.0000 | 32.4785 | 1.7075 | -0.4016 | 8.7115 | 1.7771 |

## Return correlations (50bps)

| index | index | LS57 | LS82_CARRY | LS88_LONG_CARRY | LS89_MA21 |
| --- | --- | --- | --- | --- | --- |
| 0 | LS57 | 1.0000 | 0.9952 | 0.9934 | 0.9834 |
| 1 | LS82_CARRY | 0.9952 | 1.0000 | 0.9910 | 0.9781 |
| 2 | LS88_LONG_CARRY | 0.9934 | 0.9910 | 1.0000 | 0.9741 |
| 3 | LS89_MA21 | 0.9834 | 0.9781 | 0.9741 | 1.0000 |

## Decision

50bps LS57: 34.6316x / 1.7012 / -43.4422%; PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE: 33.5719x / 1.6862 / -43.0244%.
Primary ensemble gate: **FAIL**.

Research output only; no orders sent.
