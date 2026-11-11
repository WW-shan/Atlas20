# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | H5_BASELINE | LS10_H5_RELMOM14_RISKBUDGET_FUNDING_EXIT |
| --- | --- | --- |
| 2022 | -0.1574 | -0.1338 |
| 2023 | 2.0114 | 2.0216 |
| 2024 | 0.9461 | 0.9602 |
| 2025 | 1.1235 | 1.1202 |
| 2026 | 1.0360 | 1.0360 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | H5_BASELINE | -0.1574 |
| 1 | LS10_H5_RELMOM14_RISKBUDGET_FUNDING_EXIT | -0.1338 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 2,022.0000 | 1,359.0000 | 25.3369 | 2.0680 |
| 1 | H5_BASELINE | 2,023.0000 | 1,359.0000 | 7.0894 | 1.5419 |
| 2 | H5_BASELINE | 2,024.0000 | 1,358.0000 | 10.9698 | 1.7981 |
| 3 | H5_BASELINE | 2,025.0000 | 1,359.0000 | 10.0538 | 1.6957 |
| 4 | H5_BASELINE | 2,026.0000 | 1,461.0000 | 10.4858 | 1.5638 |
| 5 | LS10_H5_RELMOM14_RISKBUDGET_FUNDING_EXIT | 2,022.0000 | 1,359.0000 | 25.5676 | 2.0760 |
| 6 | LS10_H5_RELMOM14_RISKBUDGET_FUNDING_EXIT | 2,023.0000 | 1,359.0000 | 7.3293 | 1.5668 |
| 7 | LS10_H5_RELMOM14_RISKBUDGET_FUNDING_EXIT | 2,024.0000 | 1,358.0000 | 11.2976 | 1.8189 |
| 8 | LS10_H5_RELMOM14_RISKBUDGET_FUNDING_EXIT | 2,025.0000 | 1,359.0000 | 10.4453 | 1.7235 |
| 9 | LS10_H5_RELMOM14_RISKBUDGET_FUNDING_EXIT | 2,026.0000 | 1,461.0000 | 10.8774 | 1.5871 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 365.0000 | 2022-05-12 | 2.1634 | 0.7970 |
| 1 | LS10_H5_RELMOM14_RISKBUDGET_FUNDING_EXIT | 365.0000 | 2022-05-12 | 2.1782 | 0.7946 |
