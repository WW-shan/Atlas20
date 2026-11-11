# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | H5_BASELINE | LS2_H5_MONTHLY_SECTOR |
| --- | --- | --- |
| 2022 | -0.1574 | 0.0512 |
| 2023 | 2.0114 | 1.4946 |
| 2024 | 0.9461 | -0.0453 |
| 2025 | 1.1235 | 0.5778 |
| 2026 | 1.0360 | 0.5632 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | H5_BASELINE | -0.1574 |
| 1 | LS2_H5_MONTHLY_SECTOR | -0.0453 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 2,022.0000 | 1,359.0000 | 25.3369 | 2.0680 |
| 1 | H5_BASELINE | 2,023.0000 | 1,359.0000 | 7.0894 | 1.5419 |
| 2 | H5_BASELINE | 2,024.0000 | 1,358.0000 | 10.9698 | 1.7981 |
| 3 | H5_BASELINE | 2,025.0000 | 1,359.0000 | 10.0538 | 1.6957 |
| 4 | H5_BASELINE | 2,026.0000 | 1,461.0000 | 10.4858 | 1.5638 |
| 5 | LS2_H5_MONTHLY_SECTOR | 2,022.0000 | 1,359.0000 | 5.8740 | 1.3540 |
| 6 | LS2_H5_MONTHLY_SECTOR | 2,023.0000 | 1,359.0000 | 2.4753 | 0.8784 |
| 7 | LS2_H5_MONTHLY_SECTOR | 2,024.0000 | 1,358.0000 | 6.4676 | 1.5902 |
| 8 | LS2_H5_MONTHLY_SECTOR | 2,025.0000 | 1,359.0000 | 3.9136 | 1.1512 |
| 9 | LS2_H5_MONTHLY_SECTOR | 2,026.0000 | 1,461.0000 | 3.9502 | 1.0910 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 365.0000 | 2022-05-12 | 2.1634 | 0.7970 |
| 1 | LS2_H5_MONTHLY_SECTOR | 365.0000 | 2023-12-17 | 1.5269 | 0.7671 |
