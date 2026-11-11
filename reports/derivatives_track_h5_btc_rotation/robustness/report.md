# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | L125_BASELINE | LS14_H5_WEAK_ROTATE_BTC25 |
| --- | --- | --- |
| 2022 | -0.1961 | 0.1578 |
| 2023 | 2.7720 | 2.1706 |
| 2024 | 1.1925 | 0.8963 |
| 2025 | 1.5102 | 1.5472 |
| 2026 | 1.4101 | 1.4553 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | L125_BASELINE | -0.1961 |
| 1 | LS14_H5_WEAK_ROTATE_BTC25 | 0.1578 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | L125_BASELINE | 2,022.0000 | 1,359.0000 | 50.0330 | 2.0657 |
| 1 | L125_BASELINE | 2,023.0000 | 1,359.0000 | 10.6628 | 1.5431 |
| 2 | L125_BASELINE | 2,024.0000 | 1,358.0000 | 18.3441 | 1.7969 |
| 3 | L125_BASELINE | 2,025.0000 | 1,359.0000 | 16.0225 | 1.6888 |
| 4 | L125_BASELINE | 2,026.0000 | 1,461.0000 | 16.6884 | 1.5578 |
| 5 | LS14_H5_WEAK_ROTATE_BTC25 | 2,022.0000 | 1,359.0000 | 37.6007 | 2.0795 |
| 6 | LS14_H5_WEAK_ROTATE_BTC25 | 2,023.0000 | 1,359.0000 | 13.7302 | 1.7488 |
| 7 | LS14_H5_WEAK_ROTATE_BTC25 | 2,024.0000 | 1,358.0000 | 22.9571 | 2.0322 |
| 8 | LS14_H5_WEAK_ROTATE_BTC25 | 2,025.0000 | 1,359.0000 | 17.0906 | 1.8515 |
| 9 | LS14_H5_WEAK_ROTATE_BTC25 | 2,026.0000 | 1,461.0000 | 17.7301 | 1.6922 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | L125_BASELINE | 365.0000 | 2022-05-12 | 2.5547 | 0.7325 |
| 1 | LS14_H5_WEAK_ROTATE_BTC25 | 365.0000 | 2022-06-23 | 2.4901 | 0.8290 |
