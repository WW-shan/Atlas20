# Top20 membership churn short backtest

- status: research only; no orders; no live changes
- event: confirmed Top20 entry or exit; short changed coins, long BTC hedge
- execution: event close → next close; all event-day tranches equal-weight; gross <=1
- costs: 2/20/50/100bps per side; funding excluded in this screen

## Discovery-ranked cells

| index | variant_id | discovery_multiple_20 | discovery_sharpe_20 | discovery_sharpe_50 | validation_multiple_20 | validation_sharpe_20 | pre2022_sharpe_20 | full_multiple_20 | full_sharpe_20 | full_max_drawdown_20 | turnover_20 | events |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | CHURN_m7_h28 | 1.0697 | 1.2246 | 0.9450 | 1.1325 | 1.3552 | -2.6950 | 0.9212 | -0.2542 | -0.2602 | 17.2946 | 364.0000 |
| 1 | CHURN_m3_h28 | 1.0872 | 1.2237 | 0.9538 | 1.1185 | 1.0383 | -2.3168 | 0.9501 | -0.1315 | -0.2416 | 20.7321 | 464.0000 |
| 2 | CHURN_m7_h14 | 1.0930 | 1.1437 | 0.7466 | 1.0588 | 0.5153 | -2.2377 | 0.9260 | -0.2130 | -0.2168 | 34.9821 | 364.0000 |
| 3 | CHURN_m3_h14 | 1.0937 | 1.0544 | 0.6151 | 1.0389 | 0.2953 | -1.3200 | 0.9703 | -0.0484 | -0.1855 | 41.6786 | 464.0000 |
| 4 | CHURN_m14_h14 | 1.0807 | 0.9952 | 0.6479 | 1.0676 | 0.6856 | -1.7474 | 0.8916 | -0.2547 | -0.2377 | 29.5714 | 287.0000 |
| 5 | CHURN_m7_h56 | 1.0426 | 0.9182 | 0.7450 | 1.0625 | 0.7705 | -2.4406 | 0.9271 | -0.3185 | -0.1869 | 8.6875 | 364.0000 |
| 6 | CHURN_m7_h7 | 1.0787 | 0.9166 | 0.1880 | 1.0328 | 0.2403 | -2.4326 | 0.8200 | -0.4658 | -0.3073 | 70.0000 | 364.0000 |
| 7 | CHURN_m3_h56 | 1.0441 | 0.7593 | 0.5920 | 1.0595 | 0.6093 | -2.0805 | 0.9381 | -0.2285 | -0.1828 | 10.3750 | 464.0000 |
| 8 | CHURN_m3_h7 | 1.0742 | 0.6568 | 0.0218 | 0.9339 | -0.3481 | -1.4518 | 0.8014 | -0.4182 | -0.2353 | 81.9714 | 464.0000 |
| 9 | CHURN_m14_h7 | 1.0752 | 0.6210 | 0.1853 | 0.9991 | 0.0140 | -1.4710 | 0.9219 | -0.1903 | -0.1847 | 60.4286 | 287.0000 |
| 10 | CHURN_m14_h28 | 1.0260 | 0.4625 | 0.2211 | 1.0879 | 1.0811 | -1.8166 | 0.9524 | -0.1684 | -0.1796 | 14.3571 | 287.0000 |
| 11 | CHURN_m14_h56 | 1.0063 | 0.1556 | -0.0041 | 1.0440 | 0.6346 | -1.4932 | 0.9551 | -0.2176 | -0.1204 | 7.3036 | 287.0000 |

## Selected by discovery only

`CHURN_m7_h28`

## Acceptance checks

- [x] `validation_sharpe_20_positive`
- [x] `validation_sharpe_50_positive`
- [ ] `pre2022_sharpe_20_positive`
- [ ] `full_multiple_20_above_one`
- [ ] `full_multiple_50_above_one`
- [ ] `full_sharpe_20_above_0_5`
- [x] `full_mdd_20_no_worse_than_minus_30pct`

## Sample metrics

| index | series | sample | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | top20_churn_short_20bps | full | 0.9212 | -0.0139 | -0.2542 | -0.2602 |
| 1 | top20_churn_short_20bps | discovery | 1.0697 | 0.0343 | 1.2246 | -0.0301 |
| 2 | top20_churn_short_20bps | validation | 1.1325 | 0.0444 | 1.3552 | -0.0318 |
| 3 | top20_churn_short_20bps | pre2022 | 0.7604 | -0.2401 | -2.6950 | -0.2602 |

## Asset contribution before costs

| index | asset | pnl_before_costs |
| --- | --- | --- |
| 0 | bitcoin | 0.2112 |
| 1 | internet-computer | 0.0166 |
| 2 | ftx-token | 0.0126 |
| 3 | flow | 0.0121 |
| 4 | the-open-network | 0.0120 |
| 5 | mantle | 0.0112 |
| 6 | kaspa | 0.0091 |
| 7 | render-token | 0.0090 |
| 8 | stellar | 0.0089 |
| 9 | ethereum-classic | 0.0083 |
| 10 | decentraland | 0.0066 |
| 11 | pancakeswap-token | 0.0060 |
| 12 | hedera-hashgraph | 0.0058 |
| 13 | immutable-x | 0.0040 |
| 14 | cosmos | 0.0039 |
| 15 | fantom | 0.0037 |
| 16 | bitway | 0.0036 |
| 17 | zcash | 0.0033 |
| 18 | elrond-erd-2 | 0.0032 |
| 19 | canton-network | 0.0031 |

## Return-space LS57 overlay

Overlay rows add the churn sleeve to LS57 without modelling margin, gross, funding or execution.

| index | series | sample | multiple | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | ls57_20bps | full | 68.8077 | 1.4507 | 1.9819 | -0.3984 |
| 1 | ls57_20bps | discovery | 4.5154 | 1.1271 | 1.7976 | -0.3984 |
| 2 | ls57_20bps | validation | 15.2386 | 1.7216 | 2.1079 | -0.3231 |
| 3 | ls57_plus_10pct_churn | full | 70.1350 | 1.4606 | 1.9905 | -0.3964 |
| 4 | ls57_plus_10pct_churn | discovery | 4.5452 | 1.1342 | 1.8040 | -0.3964 |
| 5 | ls57_plus_10pct_churn | validation | 15.4304 | 1.7341 | 2.1180 | -0.3187 |
| 6 | ls57_plus_20pct_churn | full | 71.4850 | 1.4706 | 1.9991 | -0.3944 |
| 7 | ls57_plus_20pct_churn | discovery | 4.5753 | 1.1412 | 1.8102 | -0.3944 |
| 8 | ls57_plus_20pct_churn | validation | 15.6242 | 1.7467 | 2.1281 | -0.3144 |

## Guardrail

The event detector is point-in-time, but the Top20 boundary can be noisy. Missing returns are counted and zero-filled in this screen. A pass needs Bitget mark/fill, funding and partial-fill verification before shadow promotion.
