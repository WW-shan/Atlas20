# Gated Top20 membership churn short

- frozen event rule: m=7, h=28, entry+exit, BTC-hedged churn
- gates: alt_rel_60, btc_ma200, both; all three reported
- execution: event close → next close; total gross <=1
- costs: 2/20/50/100bps per side; funding excluded

## Gate results

| index | variant_id | events | discovery_multiple_20 | discovery_sharpe_20 | discovery_sharpe_50 | validation_multiple_20 | validation_sharpe_20 | pre2022_multiple_20 | pre2022_sharpe_20 | full_multiple_20 | full_sharpe_20 | full_max_drawdown_20 | turnover_20 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | alt_rel_60 | 364.0000 | 1.0400 | 0.9978 | 0.7490 | 1.0341 | 0.6509 | 0.9864 | -1.1047 | 1.0608 | 0.5686 | -0.0256 | 7.2321 |
| 1 | btc_ma200 | 364.0000 | 1.0297 | 0.6461 | 0.4339 | 1.0428 | 0.9534 | 0.9998 | -0.0089 | 1.0736 | 0.6840 | -0.0301 | 6.6607 |
| 2 | both | 364.0000 | 1.0022 | 0.0763 | -0.0919 | 1.0152 | 0.4579 | 0.9873 | -1.3875 | 1.0045 | 0.0655 | -0.0246 | 3.6607 |

## Selected by discovery only

`alt_rel_60`

## Acceptance checks

- [x] `validation_sharpe_20_positive`
- [x] `validation_sharpe_50_positive`
- [x] `pre2022_multiple_at_least_0_92`
- [x] `full_multiple_20_above_one`
- [x] `full_multiple_50_above_one`
- [x] `full_sharpe_20_above_0_5`
- [x] `full_mdd_20_no_worse_than_minus_30pct`

## Sample metrics

| index | series | sample | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | churn_gate_alt_rel_60_20bps | full | 1.0608 | 0.0101 | 0.5686 | -0.0256 |
| 1 | churn_gate_alt_rel_60_20bps | discovery | 1.0400 | 0.0198 | 0.9978 | -0.0204 |
| 2 | churn_gate_alt_rel_60_20bps | validation | 1.0341 | 0.0118 | 0.6509 | -0.0256 |
| 3 | churn_gate_alt_rel_60_20bps | pre2022 | 0.9864 | -0.0137 | -1.1047 | -0.0218 |

## Return-space LS57 overlay

| index | series | sample | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | ls57_plus_10pct_churn_gate | full | 69.3334 | 1.4546 | 1.9853 | -0.3967 |
| 1 | ls57_plus_10pct_churn_gate | discovery | 4.5328 | 1.1312 | 1.8013 | -0.3967 |
| 2 | ls57_plus_10pct_churn_gate | validation | 15.2961 | 1.7253 | 2.1110 | -0.3210 |
| 3 | ls57_plus_20pct_churn_gate | full | 69.8619 | 1.4586 | 1.9886 | -0.3951 |
| 4 | ls57_plus_20pct_churn_gate | discovery | 4.5502 | 1.1353 | 1.8050 | -0.3951 |
| 5 | ls57_plus_20pct_churn_gate | validation | 15.3537 | 1.7291 | 2.1140 | -0.3188 |

## Guardrail

The gate is evaluated only on the event date. A pass needs funding, Bitget mark/fill and forward OOS verification before shadow promotion.
