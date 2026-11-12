# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 3

## Yearly returns

| year | L125_BASELINE | LS23_H5_PROFIT_LOCK_REGIME_SHORT | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE |
| --- | --- | --- | --- |
| 2022 | -0.1961 | 0.2371 | 0.2371 |
| 2023 | 2.7720 | 2.6498 | 2.6492 |
| 2024 | 1.1925 | 0.8033 | 1.0846 |
| 2025 | 1.5102 | 1.9407 | 1.7534 |
| 2026 | 1.4101 | 1.5857 | 1.5399 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | L125_BASELINE | -0.1961 |
| 1 | LS23_H5_PROFIT_LOCK_REGIME_SHORT | 0.2371 |
| 2 | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE | 0.2371 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | L125_BASELINE | 2,022.0000 | 1,359.0000 | 50.0330 | 2.0657 |
| 1 | L125_BASELINE | 2,023.0000 | 1,359.0000 | 10.6628 | 1.5431 |
| 2 | L125_BASELINE | 2,024.0000 | 1,358.0000 | 18.3441 | 1.7969 |
| 3 | L125_BASELINE | 2,025.0000 | 1,359.0000 | 16.0225 | 1.6888 |
| 4 | L125_BASELINE | 2,026.0000 | 1,461.0000 | 16.6884 | 1.5578 |
| 5 | LS23_H5_PROFIT_LOCK_REGIME_SHORT | 2,022.0000 | 1,359.0000 | 50.0467 | 2.1231 |
| 6 | LS23_H5_PROFIT_LOCK_REGIME_SHORT | 2,023.0000 | 1,359.0000 | 16.9638 | 1.8325 |
| 7 | LS23_H5_PROFIT_LOCK_REGIME_SHORT | 2,024.0000 | 1,358.0000 | 34.3343 | 2.1470 |
| 8 | LS23_H5_PROFIT_LOCK_REGIME_SHORT | 2,025.0000 | 1,359.0000 | 21.0546 | 1.8795 |
| 9 | LS23_H5_PROFIT_LOCK_REGIME_SHORT | 2,026.0000 | 1,461.0000 | 23.9447 | 1.7578 |
| 10 | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE | 2,022.0000 | 1,359.0000 | 53.1989 | 2.1395 |
| 11 | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE | 2,023.0000 | 1,359.0000 | 18.0353 | 1.8519 |
| 12 | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE | 2,024.0000 | 1,358.0000 | 31.5714 | 2.0946 |
| 13 | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE | 2,025.0000 | 1,359.0000 | 23.9034 | 1.9376 |
| 14 | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE | 2,026.0000 | 1,461.0000 | 25.9128 | 1.7853 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | L125_BASELINE | 365.0000 | 2022-05-12 | 2.5547 | 0.7325 |
| 1 | LS23_H5_PROFIT_LOCK_REGIME_SHORT | 365.0000 | 2022-06-23 | 2.8034 | 0.8551 |
| 2 | LS42_H5_LS23_PROFITLOCK_REDISTRIBUTE | 365.0000 | 2022-06-23 | 2.7041 | 0.8508 |
