# Top20 churn short with full-gross event tranches

- frozen LS73 event rule: m=7, h=28, alt_rel_60 gate, BTC-hedged entry+exit churn
- only change: normalize each active day to gross 1.0; no events means cash
- total gross remains <=1.0; no added leverage
- costs: 2/20/50/100bps per side; funding excluded

## Selected scenario

| index | field | value |
| --- | --- | --- |
| 0 | variant_id | CHURN_FULLGROSS_m7_h28_alt_rel_60 |
| 1 | confirmation_days | 7 |
| 2 | hold_days | 28 |
| 3 | turnover_20 | 82.18809523809524 |
| 4 | average_active_gross_20 | 0.5340802987861811 |
| 5 | max_gross_20 | 1.0000000000000002 |
| 6 | missing_20 | 0 |
| 7 | full_multiple_20 | 1.4819658985659587 |
| 8 | full_cagr_20 | 0.06936184218516961 |
| 9 | full_sharpe_20 | 0.4529596804205595 |
| 10 | full_max_drawdown_20 | -0.22652531699529044 |
| 11 | full_multiple_50 | 1.1576864812582346 |
| 12 | full_sharpe_50 | 0.2271319912920816 |
| 13 | discovery_multiple_20 | 1.3079392806864074 |
| 14 | discovery_cagr_20 | 0.14386232365313822 |
| 15 | discovery_sharpe_20 | 0.90277150955731 |
| 16 | discovery_max_drawdown_20 | -0.15767576867777422 |
| 17 | discovery_multiple_50 | 1.1884499918142966 |
| 18 | discovery_sharpe_50 | 0.6112896696428445 |
| 19 | validation_multiple_20 | 1.2961686346513355 |
| 20 | validation_cagr_20 | 0.09474520109397933 |
| 21 | validation_sharpe_20 | 0.5381021883927433 |
| 22 | validation_max_drawdown_20 | -0.21287021203596157 |
| 23 | validation_multiple_50 | 1.1369231060423226 |
| 24 | validation_sharpe_50 | 0.31844289431253675 |
| 25 | pre2022_multiple_20 | 0.8741563553334198 |
| 26 | pre2022_cagr_20 | -0.12616658102691836 |
| 27 | pre2022_sharpe_20 | -0.7600859394008831 |
| 28 | pre2022_max_drawdown_20 | -0.22652531699529044 |
| 29 | pre2022_multiple_50 | 0.8567990120148331 |
| 30 | pre2022_sharpe_50 | -0.8835418681700328 |

## Acceptance checks

- [x] `discovery_sharpe_20_positive`
- [x] `validation_sharpe_20_positive`
- [ ] `pre2022_multiple_at_least_0_92`
- [x] `full_multiple_20_above_one`
- [x] `full_multiple_50_above_one`
- [ ] `full_sharpe_20_above_0_5`
- [x] `full_mdd_20_no_worse_than_minus_30pct`
- [x] `full_multiple_at_least_1_10x_ls73`

## Sample metrics

| index | series | sample | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | churn_fullgross_20bps | full | 1.4820 | 0.0694 | 0.4530 | -0.2265 |
| 1 | churn_fullgross_20bps | discovery | 1.3079 | 0.1439 | 0.9028 | -0.1577 |
| 2 | churn_fullgross_20bps | validation | 1.2962 | 0.0947 | 0.5381 | -0.2129 |
| 3 | churn_fullgross_20bps | pre2022 | 0.8742 | -0.1262 | -0.7601 | -0.2265 |

## Asset contribution before costs

| index | asset | pnl_before_costs |
| --- | --- | --- |
| 0 | bitcoin | 1.2533 |
| 1 | monero | 0.1286 |
| 2 | internet-computer | 0.0798 |
| 3 | mantle | 0.0789 |
| 4 | zcash | 0.0549 |
| 5 | kaspa | 0.0524 |
| 6 | crypto-com-chain | 0.0501 |
| 7 | cosmos | 0.0419 |
| 8 | render-token | 0.0416 |
| 9 | pepe | 0.0406 |
| 10 | bitget-token | 0.0333 |
| 11 | okb | 0.0301 |
| 12 | flow | 0.0271 |
| 13 | canton-network | 0.0242 |
| 14 | filecoin | 0.0204 |
| 15 | tron | 0.0141 |
| 16 | lido-dao | 0.0109 |
| 17 | chainlink | 0.0061 |
| 18 | matic-network | 0.0039 |
| 19 | neo | 0.0000 |

## Return-space LS57 overlay

| index | series | sample | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | ls57_plus_10pct_fullgross | full | 73.4385 | 1.4847 | 2.0118 | -0.3856 |
| 1 | ls57_plus_10pct_fullgross | discovery | 4.6472 | 1.1580 | 1.8256 | -0.3856 |
| 2 | ls57_plus_10pct_fullgross | validation | 15.8026 | 1.7582 | 2.1391 | -0.3121 |
| 3 | ls57_plus_20pct_fullgross | full | 78.2480 | 1.5183 | 2.0389 | -0.3727 |
| 4 | ls57_plus_20pct_fullgross | discovery | 4.7804 | 1.1888 | 1.8514 | -0.3727 |
| 5 | ls57_plus_20pct_fullgross | validation | 16.3684 | 1.7941 | 2.1674 | -0.3010 |

## Guardrail

Full-gross normalization increases per-event concentration relative to LS73. The result is not live-ready without funding, Bitget mark/fill, per-coin caps and forward OOS verification.
