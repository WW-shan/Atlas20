# Daily BTC shock relative-gap diagnostic

- status: gross event study only; no orders; no costs applied to the spread
- sample: 2022-01-01 → 2026-11-12
- discovery: 2022-01-01 → 2023-12-31; validation: 2024-01-01 → 2026-11-12
- beta: 120D rolling BTC beta, minimum 90 daily returns
- signal/future windows: 1/3/5/10 days; tails: 10% and 20%
- shock buckets: all, |z|>=2.0, |z|>=2.5
- backtest cost buffer: round-trip 40bps + 10bps

## Discovery-ranked cells

Cells are ranked by discovery contrarian spread only. Validation is shown for the same cells and was not used to choose the windows.

| index | signal_days | future_days | bucket | tail_fraction | n_obs | ic_mean | contrarian_spread_mean_bps | spread_tstat | spread_positive_share | tier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 10.0000 | 3.0000 | abs_z_ge_2_5 | 0.1000 | 34.0000 | 0.0439 | -0.7542 | -0.0091 | 0.5882 | rejected-now |
| 1 | 10.0000 | 1.0000 | abs_z_ge_2_5 | 0.1000 | 34.0000 | 0.0525 | -24.0232 | -0.5187 | 0.5000 | rejected-now |
| 2 | 10.0000 | 5.0000 | abs_z_ge_2_5 | 0.1000 | 34.0000 | 0.0947 | -24.2795 | -0.2307 | 0.4412 | rejected-now |
| 3 | 10.0000 | 1.0000 | abs_z_ge_2_5 | 0.2000 | 34.0000 | 0.0525 | -37.9959 | -1.2910 | 0.5000 | rejected-now |
| 4 | 5.0000 | 1.0000 | all | 0.2000 | 636.0000 | -0.0227 | -44.8701 | -1.7195 | 0.5094 | rejected-now |
| 5 | 1.0000 | 1.0000 | all | 0.2000 | 640.0000 | -0.0047 | -45.8708 | -1.8102 | 0.4922 | rejected-now |
| 6 | 3.0000 | 1.0000 | all | 0.2000 | 638.0000 | -0.0319 | -47.0782 | -1.7914 | 0.5031 | rejected-now |
| 7 | 10.0000 | 3.0000 | abs_z_ge_2_5 | 0.2000 | 34.0000 | 0.0439 | -54.9727 | -1.0024 | 0.3529 | rejected-now |
| 8 | 10.0000 | 1.0000 | all | 0.2000 | 631.0000 | -0.0125 | -60.7493 | -2.3254 | 0.5008 | rejected-now |
| 9 | 10.0000 | 10.0000 | abs_z_ge_2_5 | 0.1000 | 34.0000 | 0.0229 | -67.2800 | -0.4433 | 0.5294 | rejected-now |
| 10 | 3.0000 | 1.0000 | all | 0.1000 | 638.0000 | -0.0319 | -82.1030 | -1.5786 | 0.5204 | rejected-now |
| 11 | 1.0000 | 1.0000 | all | 0.1000 | 640.0000 | -0.0047 | -88.1953 | -1.7834 | 0.5031 | rejected-now |
| 12 | 10.0000 | 5.0000 | abs_z_ge_2_5 | 0.2000 | 34.0000 | 0.0947 | -92.8174 | -1.4799 | 0.2647 | rejected-now |
| 13 | 5.0000 | 1.0000 | all | 0.1000 | 636.0000 | -0.0227 | -97.3161 | -1.9165 | 0.5047 | rejected-now |
| 14 | 10.0000 | 1.0000 | all | 0.1000 | 631.0000 | -0.0125 | -104.5744 | -2.0159 | 0.4913 | rejected-now |
| 15 | 3.0000 | 3.0000 | all | 0.2000 | 638.0000 | -0.0352 | -145.2514 | -2.1097 | 0.5125 | rejected-now |

## Validation for the same cells

Among the 16 discovery-ranked cells, **0/16** have negative IC and positive contrarian spread in both periods.

| index | signal_days | future_days | bucket | tail_fraction | n_obs | ic_mean | contrarian_spread_mean_bps | spread_tstat | spread_positive_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 10.0000 | 10.0000 | abs_z_ge_2_5 | 0.1000 | 42.0000 | 0.0157 | 416.2477 | 1.5755 | 0.5238 |
| 1 | 10.0000 | 5.0000 | abs_z_ge_2_5 | 0.1000 | 42.0000 | 0.0345 | 130.8847 | 0.8567 | 0.4762 |
| 2 | 10.0000 | 3.0000 | abs_z_ge_2_5 | 0.1000 | 42.0000 | 0.0030 | 121.8818 | 0.9393 | 0.5238 |
| 3 | 5.0000 | 1.0000 | all | 0.1000 | 1,045.0000 | -0.0233 | 3.0802 | 0.2444 | 0.5187 |
| 4 | 3.0000 | 1.0000 | all | 0.2000 | 1,045.0000 | -0.0196 | -2.0607 | -0.2462 | 0.4957 |
| 5 | 3.0000 | 1.0000 | all | 0.1000 | 1,045.0000 | -0.0196 | -2.5322 | -0.2007 | 0.5120 |
| 6 | 1.0000 | 1.0000 | all | 0.2000 | 1,045.0000 | -0.0110 | -3.1636 | -0.3992 | 0.5129 |
| 7 | 10.0000 | 1.0000 | all | 0.2000 | 1,045.0000 | -0.0215 | -5.0561 | -0.5838 | 0.5053 |
| 8 | 5.0000 | 1.0000 | all | 0.2000 | 1,045.0000 | -0.0233 | -5.9056 | -0.6829 | 0.5062 |
| 9 | 10.0000 | 1.0000 | all | 0.1000 | 1,045.0000 | -0.0215 | -6.4118 | -0.5099 | 0.5091 |
| 10 | 10.0000 | 1.0000 | abs_z_ge_2_5 | 0.1000 | 42.0000 | 0.0398 | -9.6163 | -0.0882 | 0.5238 |
| 11 | 1.0000 | 1.0000 | all | 0.1000 | 1,045.0000 | -0.0110 | -10.8238 | -0.8369 | 0.5005 |
| 12 | 3.0000 | 3.0000 | all | 0.2000 | 1,043.0000 | -0.0080 | -12.2980 | -0.8535 | 0.5168 |
| 13 | 10.0000 | 3.0000 | abs_z_ge_2_5 | 0.2000 | 42.0000 | 0.0030 | -74.9865 | -0.8898 | 0.4762 |
| 14 | 10.0000 | 1.0000 | abs_z_ge_2_5 | 0.2000 | 42.0000 | 0.0398 | -80.8927 | -1.2780 | 0.4286 |
| 15 | 10.0000 | 5.0000 | abs_z_ge_2_5 | 0.2000 | 42.0000 | 0.0345 | -91.2858 | -0.8814 | 0.4048 |

## Interpretation

Daily observations overlap for horizons above one day, so the t-stat is descriptive, not an independent-sample test. A candidate label requires the discovery and validation gross spread to exceed a 50bps combined cost-and-buffer threshold. Any candidate still needs a proper T+1 close backtest, funding, slippage and a non-overlapping event scheduler before it can be considered for live integration.
