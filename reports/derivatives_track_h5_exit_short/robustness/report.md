# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | H5_BASELINE | LS3_H5_EXIT_SHORT21 |
| --- | --- | --- |
| 2022 | -0.1574 | 0.2346 |
| 2023 | 2.0114 | 1.8534 |
| 2024 | 0.9461 | 1.5638 |
| 2025 | 1.1235 | 1.3636 |
| 2026 | 1.0360 | 1.1511 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | H5_BASELINE | -0.1574 |
| 1 | LS3_H5_EXIT_SHORT21 | 0.2346 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 2,022.0000 | 1,359.0000 | 25.3369 | 2.0680 |
| 1 | H5_BASELINE | 2,023.0000 | 1,359.0000 | 7.0894 | 1.5419 |
| 2 | H5_BASELINE | 2,024.0000 | 1,358.0000 | 10.9698 | 1.7981 |
| 3 | H5_BASELINE | 2,025.0000 | 1,359.0000 | 10.0538 | 1.6957 |
| 4 | H5_BASELINE | 2,026.0000 | 1,461.0000 | 10.4858 | 1.5638 |
| 5 | LS3_H5_EXIT_SHORT21 | 2,022.0000 | 1,359.0000 | 37.1948 | 2.0320 |
| 6 | LS3_H5_EXIT_SHORT21 | 2,023.0000 | 1,359.0000 | 16.0928 | 1.7237 |
| 7 | LS3_H5_EXIT_SHORT21 | 2,024.0000 | 1,358.0000 | 17.9107 | 1.8163 |
| 8 | LS3_H5_EXIT_SHORT21 | 2,025.0000 | 1,359.0000 | 19.4277 | 1.8118 |
| 9 | LS3_H5_EXIT_SHORT21 | 2,026.0000 | 1,461.0000 | 21.3463 | 1.6789 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 365.0000 | 2022-05-12 | 2.1634 | 0.7970 |
| 1 | LS3_H5_EXIT_SHORT21 | 365.0000 | 2022-05-13 | 2.5089 | 0.5957 |
