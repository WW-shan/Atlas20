# Intraday BTC shock lead-lag backtest

- status: research backtest only; no orders; no live changes
- sample: 2022-01-01 → 2026-09-30
- execution: signal close -> next 30m open; hold 2h or 4h; gross <= 1.0x
- costs: 6/12/20bps per one-way gross turnover; funding excluded
- discovery: 2022-01-01 → 2023-12-31; validation: 2024-01-01 → 2026-09-30

## Variant summary

| index | variant_id | tier | events | average_active_gross | max_active_gross | turnover | missing_return_observations | full_multiple_6 | full_sharpe_6 | full_mdd_6 | validation_sharpe_6 | full_multiple_12 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LL_1_4 | rejected-now | 2,465.0000 | 0.0296 | 1.0000 | 1,232.5000 | 0.0000 | 0.5691 | -2.6943 | -0.4369 | -3.0324 | 0.2716 |
| 1 | LL_2_4 | rejected-now | 2,629.0000 | 0.0316 | 1.0000 | 1,314.5000 | 0.0000 | 0.5426 | -2.9473 | -0.4638 | -3.1720 | 0.2465 |
| 2 | LL_2_8 | rejected-now | 2,629.0000 | 0.0316 | 1.0000 | 657.2500 | 0.0000 | 0.7334 | -2.2439 | -0.2733 | -2.3015 | 0.4944 |
| 3 | LL_4_8 | rejected-now | 2,706.0000 | 0.0325 | 1.0000 | 676.5000 | 0.0000 | 0.7800 | -1.6144 | -0.2316 | -1.9092 | 0.5197 |
| 4 | LL_ENSEMBLE | rejected-now | 10,429.0000 | 0.0313 | 0.9062 | 970.1875 | 0.0000 | 0.6490 | -2.8253 | -0.3556 | -3.0620 | 0.3626 |

## 6bps sample metrics

| index | series | sample | days | multiple | cagr | sharpe | max_drawdown | bitcoin_multiple | bitcoin_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LL_1_4 | discovery | 730.0000 | 0.8267 | -0.0909 | -2.2125 | -0.1792 | 0.8860 | 0.1655 |
| 1 | LL_1_4 | full | 1,734.0000 | 0.5691 | -0.1120 | -2.6943 | -0.4369 | 1.7523 | 0.4864 |
| 2 | LL_1_4 | validation | 1,004.0000 | 0.6883 | -0.1271 | -3.0324 | -0.3167 | 1.9777 | 0.7600 |
| 3 | LL_2_4 | discovery | 730.0000 | 0.8210 | -0.0940 | -2.6114 | -0.1853 | 0.8860 | 0.1655 |
| 4 | LL_2_4 | full | 1,734.0000 | 0.5426 | -0.1208 | -2.9473 | -0.4638 | 1.7523 | 0.4864 |
| 5 | LL_2_4 | validation | 1,004.0000 | 0.6608 | -0.1399 | -3.1720 | -0.3511 | 1.9777 | 0.7600 |
| 6 | LL_2_8 | discovery | 730.0000 | 0.8971 | -0.0529 | -2.1870 | -0.1055 | 0.8860 | 0.1655 |
| 7 | LL_2_8 | full | 1,734.0000 | 0.7334 | -0.0632 | -2.2439 | -0.2733 | 1.7523 | 0.4864 |
| 8 | LL_2_8 | validation | 1,004.0000 | 0.8175 | -0.0707 | -2.3015 | -0.1911 | 1.9777 | 0.7600 |
| 9 | LL_4_8 | discovery | 730.0000 | 0.9404 | -0.0303 | -1.1237 | -0.0732 | 0.8860 | 0.1655 |
| 10 | LL_4_8 | full | 1,734.0000 | 0.7800 | -0.0510 | -1.6144 | -0.2316 | 1.7523 | 0.4864 |
| 11 | LL_4_8 | validation | 1,004.0000 | 0.8293 | -0.0658 | -1.9092 | -0.1759 | 1.9777 | 0.7600 |
| 12 | LL_ENSEMBLE | discovery | 730.0000 | 0.8703 | -0.0672 | -2.4663 | -0.1325 | 0.8860 | 0.1655 |
| 13 | LL_ENSEMBLE | full | 1,734.0000 | 0.6490 | -0.0870 | -2.8253 | -0.3556 | 1.7523 | 0.4864 |
| 14 | LL_ENSEMBLE | validation | 1,004.0000 | 0.7457 | -0.1013 | -3.0620 | -0.2610 | 1.9777 | 0.7600 |

## Interpretation guardrail

This uses Binance 30m OHLC as a fill proxy, fixed slot sizing, equal-weight quintile legs, zero-filled missing asset bars with a reported count, and no funding. A positive result is not an executable order or a live approval. Before promotion it still needs Bitget order-book/trade-tape fills, minimum-size and partial-fill tests, funding at 8h settlement boundaries, and a fresh OOS window that was not used in the LS63 diagnostic.
