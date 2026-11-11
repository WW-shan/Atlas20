# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | H5_BASELINE | LS1_H5_H4_SECTOR20 |
| --- | --- | --- |
| 2022 | -0.1574 | -0.1540 |
| 2023 | 2.0114 | 2.7982 |
| 2024 | 0.9461 | 0.9967 |
| 2025 | 1.1235 | 1.1341 |
| 2026 | 1.0360 | 0.9180 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | H5_BASELINE | -0.1574 |
| 1 | LS1_H5_H4_SECTOR20 | -0.1540 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 2,022.0000 | 1,359.0000 | 25.3369 | 2.0680 |
| 1 | H5_BASELINE | 2,023.0000 | 1,359.0000 | 7.0894 | 1.5419 |
| 2 | H5_BASELINE | 2,024.0000 | 1,358.0000 | 10.9698 | 1.7981 |
| 3 | H5_BASELINE | 2,025.0000 | 1,359.0000 | 10.0538 | 1.6957 |
| 4 | H5_BASELINE | 2,026.0000 | 1,461.0000 | 10.4858 | 1.5638 |
| 5 | LS1_H5_H4_SECTOR20 | 2,022.0000 | 1,359.0000 | 31.0430 | 2.2130 |
| 6 | LS1_H5_H4_SECTOR20 | 2,023.0000 | 1,359.0000 | 6.9143 | 1.5534 |
| 7 | LS1_H5_H4_SECTOR20 | 2,024.0000 | 1,358.0000 | 13.1523 | 1.9374 |
| 8 | LS1_H5_H4_SECTOR20 | 2,025.0000 | 1,359.0000 | 12.3055 | 1.8497 |
| 9 | LS1_H5_H4_SECTOR20 | 2,026.0000 | 1,461.0000 | 13.6925 | 1.7238 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 365.0000 | 2022-05-12 | 2.1634 | 0.7970 |
| 1 | LS1_H5_H4_SECTOR20 | 365.0000 | 2022-01-01 | 2.1949 | 0.8460 |
