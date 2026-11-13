# Daily BTC shock relative-continuation backtest

- sample: 2021-01-01 → 2026-11-12
- discovery: 2022-01-01 → 2023-12-31
- validation: 2024-01-01 → 2026-11-12
- independent pre-2022 OOS: 2021-01-01 → 2021-12-31
- direction: long strongest relative gap / short weakest relative gap
- execution: signal close t, earliest next close t+1, all phases equally weighted
- costs: 2/20/50/100bps per side on turnover; funding not included in this screen

## Discovery-ranked cells

| index | variant_id | discovery_multiple_20 | discovery_sharpe_20 | discovery_sharpe_50 | validation_multiple_20 | validation_sharpe_20 | pre2022_sharpe_20 | full_multiple_20 | full_sharpe_20 | full_max_drawdown_20 | turnover_20 | missing_20 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 35 | BTC_CONT_k3_h3_abs_z_ge_2_5_tail20 | 1.1289 | 1.1694 | 0.7298 | 1.0651 | 0.4370 | -1.0794 | 1.1785 | 0.5933 | -0.0699 | 34.1667 | 0.0000 |
| 80 | BTC_CONT_k10_h3_abs_z_ge_2_0_tail10 | 1.2901 | 1.1496 | 0.7968 | 1.0707 | 0.2534 | 0.2249 | 1.4029 | 0.5564 | -0.1530 | 71.6667 | 0.0000 |
| 34 | BTC_CONT_k3_h3_abs_z_ge_2_5_tail10 | 1.2315 | 1.0643 | 0.8407 | 1.1469 | 0.7305 | -0.1507 | 1.4072 | 0.7903 | -0.0728 | 34.1667 | 0.0000 |
| 81 | BTC_CONT_k10_h3_abs_z_ge_2_0_tail20 | 1.1491 | 1.0635 | 0.5053 | 1.1800 | 0.7370 | -0.3578 | 1.3258 | 0.6854 | -0.0875 | 66.0833 | 0.0000 |
| 21 | BTC_CONT_k1_h10_abs_z_ge_2_0_tail20 | 1.0377 | 0.9362 | 0.2887 | 0.9474 | -0.9430 | -1.7678 | 0.9488 | -0.4395 | -0.0654 | 23.4500 | 1.0000 |
| 10 | BTC_CONT_k1_h3_abs_z_ge_2_5_tail10 | 1.1832 | 0.8607 | 0.6129 | 0.8803 | -0.8102 | 0.3130 | 1.0565 | 0.1625 | -0.1751 | 39.5000 | 0.0000 |
| 28 | BTC_CONT_k3_h1_abs_z_ge_2_5_tail10 | 1.2768 | 0.8397 | 0.4920 | 0.9935 | 0.0172 | -1.0977 | 1.2372 | 0.3773 | -0.1904 | 87.5000 | 0.0000 |
| 29 | BTC_CONT_k3_h1_abs_z_ge_2_5_tail20 | 1.1415 | 0.8130 | 0.2045 | 0.9095 | -0.4097 | -1.4091 | 1.0015 | 0.0393 | -0.1909 | 82.0000 | 0.0000 |
| 58 | BTC_CONT_k5_h3_abs_z_ge_2_5_tail10 | 1.1558 | 0.8036 | 0.5224 | 1.1855 | 0.6668 | 0.6052 | 1.3828 | 0.6748 | -0.0887 | 33.3333 | 0.0000 |
| 72 | BTC_CONT_k10_h1_all_tail10 | 1.7067 | 0.8017 | -0.8065 | 0.3552 | -0.6945 | -0.8350 | 0.2899 | -0.2245 | -0.7971 | 1,381.5000 | 0.0000 |
| 9 | BTC_CONT_k1_h3_abs_z_ge_2_0_tail20 | 1.0985 | 0.7975 | 0.1069 | 0.8953 | -0.9119 | -1.2864 | 0.9293 | -0.2286 | -0.1228 | 79.1667 | 1.0000 |
| 11 | BTC_CONT_k1_h3_abs_z_ge_2_5_tail20 | 1.0743 | 0.7497 | 0.2298 | 0.9252 | -0.8666 | 0.1904 | 0.9984 | 0.0113 | -0.0981 | 39.5000 | 0.0000 |
| 26 | BTC_CONT_k3_h1_abs_z_ge_2_0_tail10 | 1.4020 | 0.7406 | 0.3419 | 0.8767 | -0.2627 | 0.3994 | 1.2634 | 0.2991 | -0.3369 | 187.0000 | 0.0000 |
| 54 | BTC_CONT_k5_h3_all_tail10 | 1.5755 | 0.7241 | -0.3813 | 0.5506 | -0.4145 | 0.6837 | 1.0373 | 0.2237 | -0.5639 | 957.1667 | 0.0000 |
| 93 | BTC_CONT_k10_h10_abs_z_ge_2_0_tail20 | 1.0707 | 0.7171 | 0.3623 | 1.0482 | 0.3492 | -0.2793 | 1.1120 | 0.4049 | -0.0651 | 29.0750 | 0.0000 |
| 8 | BTC_CONT_k1_h3_abs_z_ge_2_0_tail10 | 1.1604 | 0.7098 | 0.3375 | 0.8405 | -0.8332 | -0.8774 | 0.9189 | -0.1237 | -0.1930 | 79.1667 | 0.0000 |

## Selected by discovery only

`BTC_CONT_k3_h3_abs_z_ge_2_5_tail20`

| index | field | value |
| --- | --- | --- |
| 0 | variant_id | BTC_CONT_k3_h3_abs_z_ge_2_5_tail20 |
| 1 | signal_days | 3 |
| 2 | horizon_days | 3 |
| 3 | shock_bucket | abs_z_ge_2_5 |
| 4 | tail_fraction | 0.2 |
| 5 | turnover_20 | 34.166666666666664 |
| 6 | average_active_gross_20 | 0.02392623716153128 |
| 7 | max_gross_20 | 1.0 |
| 8 | missing_20 | 0 |
| 9 | full_multiple_20 | 1.1785017005578755 |
| 10 | full_cagr_20 | 0.028396173655445445 |
| 11 | full_sharpe_20 | 0.5933351408487613 |
| 12 | full_max_drawdown_20 | -0.06994584385955815 |
| 13 | full_sharpe_50 | 0.23932216960232433 |
| 14 | full_multiple_50 | 1.063758041043165 |
| 15 | discovery_multiple_20 | 1.128916582095336 |
| 16 | discovery_cagr_20 | 0.06259323183103338 |
| 17 | discovery_sharpe_20 | 1.1694365180049309 |
| 18 | discovery_max_drawdown_20 | -0.020423208271202697 |
| 19 | discovery_sharpe_50 | 0.7298178698050436 |
| 20 | discovery_multiple_50 | 1.0766184895750424 |
| 21 | validation_multiple_20 | 1.065068270899957 |
| 22 | validation_cagr_20 | 0.0222410470420209 |
| 23 | validation_sharpe_20 | 0.43699443450015646 |
| 24 | validation_max_drawdown_20 | -0.06994584385955727 |
| 25 | validation_sharpe_50 | 0.1180594140182869 |
| 26 | validation_multiple_50 | 1.0141504013053388 |
| 27 | pre2022_multiple_20 | 0.9801463215516311 |
| 28 | pre2022_cagr_20 | -0.01990767497412682 |
| 29 | pre2022_sharpe_20 | -1.0793674390784334 |
| 30 | pre2022_max_drawdown_20 | -0.021871496538893975 |
| 31 | pre2022_sharpe_50 | -1.3486894772875273 |
| 32 | pre2022_multiple_50 | 0.9742684863922683 |

## Acceptance checks

- [x] `validation_sharpe_20_positive`
- [x] `validation_sharpe_50_positive`
- [ ] `pre2022_sharpe_20_positive`
- [ ] `pre2022_sharpe_50_positive`
- [ ] `full_multiple_beats_btc`
- [x] `full_mdd_no_worse_than_minus_50pct`
- [x] `full_sharpe_above_0_5`

## Sample metrics

| index | series | sample | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | ls69_selected_20bps | full | 1.1785 | 0.0284 | 0.5933 | -0.0699 |
| 1 | bitcoin_buy_hold | full | 2.4288 | 0.1633 | 0.5500 | -0.7663 |
| 2 | ls69_selected_20bps | discovery | 1.1289 | 0.0626 | 1.1694 | -0.0204 |
| 3 | bitcoin_buy_hold | discovery | 0.8863 | -0.0586 | 0.1641 | -0.6689 |
| 4 | ls69_selected_20bps | validation | 1.0651 | 0.0222 | 0.4370 | -0.0699 |
| 5 | bitcoin_buy_hold | validation | 1.6153 | 0.1821 | 0.5895 | -0.5306 |
| 6 | ls69_selected_20bps | pre2022 | 0.9801 | -0.0199 | -1.0794 | -0.0219 |
| 7 | bitcoin_buy_hold | pre2022 | 1.5764 | 0.5784 | 0.9680 | -0.5306 |

## Yearly returns

| index | year | ls69_selected_20bps | bitcoin_buy_hold |
| --- | --- | --- | --- |
| 0 | 2,021.0000 | -0.0199 | 0.5967 |
| 1 | 2,022.0000 | 0.1042 | -0.6427 |
| 2 | 2,023.0000 | 0.0223 | 1.5542 |
| 3 | 2,024.0000 | 0.1174 | 1.2105 |
| 4 | 2,025.0000 | -0.0102 | -0.0634 |
| 5 | 2,026.0000 | -0.0370 | -0.1847 |

## Asset contribution before costs

| index | asset | pnl_before_costs | share_of_abs_pnl |
| --- | --- | --- | --- |
| 0 | terra-luna | 0.1144 | 0.1785 |
| 1 | shiba-inu | 0.1012 | 0.1578 |
| 2 | crypto-com-chain | 0.0425 | 0.0663 |
| 3 | uniswap | 0.0236 | 0.0367 |
| 4 | dogecoin | 0.0213 | 0.0332 |
| 5 | bitcoin-cash | 0.0209 | 0.0326 |
| 6 | cardano | 0.0195 | 0.0304 |
| 7 | eos | 0.0167 | 0.0261 |
| 8 | hedera-hashgraph | 0.0128 | 0.0199 |
| 9 | ethereum | 0.0105 | 0.0164 |
| 10 | tron | 0.0101 | 0.0158 |
| 11 | polkadot | 0.0100 | 0.0156 |
| 12 | zcash | 0.0078 | 0.0122 |
| 13 | hyperliquid | 0.0078 | 0.0121 |
| 14 | stellar | 0.0056 | 0.0088 |
| 15 | mantle | 0.0051 | 0.0080 |
| 16 | ethereum-classic | 0.0042 | 0.0065 |
| 17 | sui | 0.0025 | 0.0040 |
| 18 | ftx-token | 0.0021 | 0.0032 |
| 19 | binancecoin | 0.0009 | 0.0014 |

## Return-space overlay with LS57

These rows add sleeve returns to LS57 without modelling margin, gross, funding or a new order path; they are diagnostic only.

| index | series | sample | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | ls57_20bps | full | 68.8077 | 1.4507 | 1.9819 | -0.3984 |
| 1 | ls57_20bps | discovery | 4.5154 | 1.1271 | 1.7976 | -0.3984 |
| 2 | ls57_20bps | validation | 15.1085 | 1.7130 | 2.1021 | -0.3231 |
| 3 | ls57_plus_10pct_ls69 | full | 70.0355 | 1.4599 | 1.9874 | -0.3988 |
| 4 | ls57_plus_10pct_ls69 | discovery | 4.5692 | 1.1398 | 1.8082 | -0.3988 |
| 5 | ls57_plus_10pct_ls69 | validation | 15.1969 | 1.7188 | 2.1042 | -0.3241 |
| 6 | ls57_plus_20pct_ls69 | full | 71.2760 | 1.4690 | 1.9926 | -0.3994 |
| 7 | ls57_plus_20pct_ls69 | discovery | 4.6235 | 1.1525 | 1.8186 | -0.3994 |
| 8 | ls57_plus_20pct_ls69 | validation | 15.2846 | 1.7246 | 2.1061 | -0.3250 |

## Interpretation guardrail

A pass only earns a funding-aware Bitget mark/fill and gross boundary study. This screen fills missing held-asset returns with zero after counting them, so any material missing count invalidates an execution-level interpretation. The discovery/validation/pre-2022 split is reported as frozen, not as a claim that overlapping holding-period returns are independent.
