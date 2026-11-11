# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | H5_BASELINE | LS4_H5_EXIT_RISK05 |
| --- | --- | --- |
| 2022 | -0.1574 | -0.1379 |
| 2023 | 2.0114 | 2.0054 |
| 2024 | 0.9461 | 0.9891 |
| 2025 | 1.1235 | 1.2369 |
| 2026 | 1.0360 | 1.0685 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | H5_BASELINE | -0.1574 |
| 1 | LS4_H5_EXIT_RISK05 | -0.1379 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 2,022.0000 | 1,359.0000 | 25.3369 | 2.0680 |
| 1 | H5_BASELINE | 2,023.0000 | 1,359.0000 | 7.0894 | 1.5419 |
| 2 | H5_BASELINE | 2,024.0000 | 1,358.0000 | 10.9698 | 1.7981 |
| 3 | H5_BASELINE | 2,025.0000 | 1,359.0000 | 10.0538 | 1.6957 |
| 4 | H5_BASELINE | 2,026.0000 | 1,461.0000 | 10.4858 | 1.5638 |
| 5 | LS4_H5_EXIT_RISK05 | 2,022.0000 | 1,359.0000 | 27.6603 | 2.1394 |
| 6 | LS4_H5_EXIT_RISK05 | 2,023.0000 | 1,359.0000 | 7.9341 | 1.6376 |
| 7 | LS4_H5_EXIT_RISK05 | 2,024.0000 | 1,358.0000 | 11.9875 | 1.8737 |
| 8 | LS4_H5_EXIT_RISK05 | 2,025.0000 | 1,359.0000 | 10.6597 | 1.7513 |
| 9 | LS4_H5_EXIT_RISK05 | 2,026.0000 | 1,461.0000 | 11.5278 | 1.6334 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 365.0000 | 2022-05-12 | 2.1634 | 0.7970 |
| 1 | LS4_H5_EXIT_RISK05 | 365.0000 | 2022-05-12 | 2.2637 | 0.7838 |
