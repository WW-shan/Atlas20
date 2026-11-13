# Intraday BTC shock lead-lag diagnostic

- status: predictive diagnostic only; no orders; no costs
- sample: 2022-01-01 → 2026-09-30
- discovery: 2022-01-01 → 2023-12-31; validation: 2024-01-01 → 2026-09-30
- bars: Binance 30m; beta: 30D rolling BTC beta, min 20D and clipped to [0,4]
- signal windows: 1/2/4/8 bars; future horizons: 1/2/4/8 bars
- shock buckets: all, |z|>=1.5, |z|>=2.5

## Discovery-ranked cells

The table ranks cells by discovery contrarian spread only. Validation is reported for the same cells and was not used to choose the signal windows or shock thresholds.

| index | signal_bars | future_bars | bucket | n_obs | ic_mean | contrarian_spread_mean_bps | spread_tstat | spread_positive_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 4.0000 | 8.0000 | abs_z_ge_2_5 | 146.0000 | -0.0701 | 20.0665 | 1.7953 | 0.5479 |
| 1 | 2.0000 | 8.0000 | abs_z_ge_2_5 | 133.0000 | -0.0967 | 16.7256 | 1.5030 | 0.6165 |
| 2 | 4.0000 | 8.0000 | abs_z_ge_1_5 | 389.0000 | -0.0696 | 13.5998 | 2.1621 | 0.5707 |
| 3 | 2.0000 | 8.0000 | abs_z_ge_1_5 | 354.0000 | -0.0729 | 12.9460 | 2.0935 | 0.5706 |
| 4 | 2.0000 | 2.0000 | abs_z_ge_2_5 | 557.0000 | -0.0688 | 11.9082 | 3.1442 | 0.5673 |
| 5 | 2.0000 | 4.0000 | abs_z_ge_2_5 | 272.0000 | -0.0634 | 11.3211 | 1.8459 | 0.5699 |
| 6 | 1.0000 | 8.0000 | abs_z_ge_2_5 | 120.0000 | -0.0375 | 10.7501 | 0.8659 | 0.5583 |
| 7 | 1.0000 | 4.0000 | abs_z_ge_2_5 | 242.0000 | -0.0715 | 10.4868 | 1.2175 | 0.5537 |
| 8 | 8.0000 | 4.0000 | abs_z_ge_2_5 | 310.0000 | -0.0397 | 10.0126 | 1.9301 | 0.5548 |
| 9 | 1.0000 | 2.0000 | abs_z_ge_2_5 | 481.0000 | -0.0739 | 9.5398 | 2.2384 | 0.5489 |
| 10 | 4.0000 | 1.0000 | abs_z_ge_2_5 | 1,099.0000 | -0.0648 | 7.2040 | 3.3225 | 0.5578 |
| 11 | 2.0000 | 1.0000 | abs_z_ge_2_5 | 1,094.0000 | -0.0666 | 7.1898 | 3.4988 | 0.5548 |

## Validation rows for the same cells

A cell is corroborated only if its IC is negative and its contrarian spread is positive in both periods. Among the 12 discovery-ranked cells, **12/12** meet that sign test.

| index | signal_bars | future_bars | bucket | n_obs | ic_mean | contrarian_spread_mean_bps | spread_tstat | spread_positive_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 4.0000 | 8.0000 | abs_z_ge_2_5 | 161.0000 | -0.0426 | 18.5679 | 1.0650 | 0.5031 |
| 1 | 2.0000 | 8.0000 | abs_z_ge_2_5 | 168.0000 | -0.0141 | 10.7794 | 0.6073 | 0.4821 |
| 2 | 4.0000 | 8.0000 | abs_z_ge_1_5 | 546.0000 | -0.0216 | 2.2507 | 0.3007 | 0.5037 |
| 3 | 2.0000 | 8.0000 | abs_z_ge_1_5 | 539.0000 | -0.0195 | 1.3093 | 0.1825 | 0.5121 |
| 4 | 2.0000 | 2.0000 | abs_z_ge_2_5 | 758.0000 | -0.0287 | 3.5513 | 0.9903 | 0.5303 |
| 5 | 2.0000 | 4.0000 | abs_z_ge_2_5 | 382.0000 | -0.0628 | 14.6965 | 1.8741 | 0.5550 |
| 6 | 1.0000 | 8.0000 | abs_z_ge_2_5 | 160.0000 | -0.0402 | 31.5093 | 1.8803 | 0.5813 |
| 7 | 1.0000 | 4.0000 | abs_z_ge_2_5 | 360.0000 | -0.0415 | 14.5269 | 1.7318 | 0.5417 |
| 8 | 8.0000 | 4.0000 | abs_z_ge_2_5 | 428.0000 | -0.0368 | 7.5911 | 1.2380 | 0.5350 |
| 9 | 1.0000 | 2.0000 | abs_z_ge_2_5 | 731.0000 | -0.0311 | 4.3023 | 1.0595 | 0.5349 |
| 10 | 4.0000 | 1.0000 | abs_z_ge_2_5 | 1,603.0000 | -0.0433 | 3.0318 | 1.6197 | 0.5390 |
| 11 | 2.0000 | 1.0000 | abs_z_ge_2_5 | 1,531.0000 | -0.0452 | 2.5624 | 1.0631 | 0.5428 |

## Interpretation

The contrarian spread is the equal-weight mean future beta-adjusted residual of the lowest-gap quintile minus the highest-gap quintile. It is not a tradable return: it assumes frictionless round trips, ignores queue/impact/funding and uses overlapping future windows only at the sampling step. A positive result must clear a separate backtest before any live integration.
