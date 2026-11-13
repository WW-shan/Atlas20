# Intraday BTC shock lead-lag single-event backtest

- status: research backtest only; no orders; no live changes
- execution: signal close -> next 30m open; one full-gross event at a time
- costs: 6/12/20bps per one-way gross turnover; funding excluded
- discoveries: LS63 predictive diagnostic, then LS64 overlapping-tranche failure

## Variant summary

| index | variant_id | tier | events | events_per_year | average_active_gross | max_active_gross | turnover | missing_return_observations | full_multiple_6 | full_sharpe_6 | full_mdd_6 | validation_sharpe_6 | full_multiple_12 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LL_1_4 | rejected-now | 1,785.0000 | 375.7895 | 0.0858 | 1.0000 | 3,570.0000 | 0.0000 | 0.1733 | -2.2867 | -0.8299 | -2.0618 | 0.0203 |
| 1 | LL_2_4 | rejected-now | 1,570.0000 | 330.5263 | 0.0755 | 1.0000 | 3,140.0000 | 0.0000 | 0.2197 | -2.1862 | -0.7838 | -2.4355 | 0.0333 |
| 2 | LL_2_8 | rejected-now | 1,321.0000 | 278.1053 | 0.1270 | 1.0000 | 2,642.0000 | 0.0000 | 0.2114 | -2.5583 | -0.8048 | -3.3451 | 0.0433 |
| 3 | LL_4_8 | rejected-now | 1,044.0000 | 219.7895 | 0.1003 | 1.0000 | 2,088.0000 | 0.0000 | 0.3754 | -1.9178 | -0.6775 | -2.9942 | 0.1071 |
| 4 | LL_ENSEMBLE | rejected-now | 5,720.0000 | 1,204.2105 | 0.0971 | 1.0000 | 2,860.0000 | 0.0000 | 0.2380 | -2.9309 | -0.7712 | -3.3758 | 0.0428 |

## 6bps sample metrics

| index | variant_id | sample | days | multiple | cagr | sharpe | max_drawdown | bitcoin_multiple | bitcoin_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LL_1_4 | discovery | 730.0000 | 0.4971 | -0.2953 | -2.8780 | -0.5116 | 0.8860 | 0.1655 |
| 1 | LL_1_4 | full | 1,734.0000 | 0.1733 | -0.3087 | -2.2867 | -0.8299 | 1.7523 | 0.4864 |
| 2 | LL_1_4 | validation | 1,004.0000 | 0.3486 | -0.3186 | -2.0618 | -0.6519 | 1.9777 | 0.7600 |
| 3 | LL_2_4 | discovery | 730.0000 | 0.6941 | -0.1671 | -1.8298 | -0.3316 | 0.8860 | 0.1655 |
| 4 | LL_2_4 | full | 1,734.0000 | 0.2197 | -0.2733 | -2.1862 | -0.7838 | 1.7523 | 0.4864 |
| 5 | LL_2_4 | validation | 1,004.0000 | 0.3165 | -0.3421 | -2.4355 | -0.6879 | 1.9777 | 0.7600 |
| 6 | LL_2_8 | discovery | 730.0000 | 0.6255 | -0.2094 | -1.6563 | -0.4053 | 0.8860 | 0.1655 |
| 7 | LL_2_8 | full | 1,734.0000 | 0.2114 | -0.2792 | -2.5583 | -0.8048 | 1.7523 | 0.4864 |
| 8 | LL_2_8 | validation | 1,004.0000 | 0.3379 | -0.3262 | -3.3451 | -0.6822 | 1.9777 | 0.7600 |
| 9 | LL_4_8 | discovery | 730.0000 | 0.9052 | -0.0486 | -0.4287 | -0.2376 | 0.8860 | 0.1655 |
| 10 | LL_4_8 | full | 1,734.0000 | 0.3754 | -0.1865 | -1.9178 | -0.6775 | 1.7523 | 0.4864 |
| 11 | LL_4_8 | validation | 1,004.0000 | 0.4147 | -0.2741 | -2.9942 | -0.5934 | 1.9777 | 0.7600 |
| 12 | LL_ENSEMBLE | discovery | 730.0000 | 0.6683 | -0.1827 | -2.2247 | -0.3533 | 0.8860 | 0.1655 |
| 13 | LL_ENSEMBLE | full | 1,734.0000 | 0.2380 | -0.2609 | -2.9309 | -0.7712 | 1.7523 | 0.4864 |
| 14 | LL_ENSEMBLE | validation | 1,004.0000 | 0.3561 | -0.3132 | -3.3758 | -0.6502 | 1.9777 | 0.7600 |

## Interpretation guardrail

The single-event construction deliberately avoids stacking stale post-shock signals. It still uses Binance 30m OHLC as a fill proxy, excludes funding, assumes a gross-1.0 tranche can be miniaturized to the live account, and zero-fills missing asset bars with an explicit count. A pass is only a shadow candidate; real Bitget fills, partial fills, minimum sizes and a fresh post-2026-09-30 OOS are still required.
