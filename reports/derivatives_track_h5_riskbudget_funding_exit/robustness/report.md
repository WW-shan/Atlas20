# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | H5_BASELINE | LS9_H5_RISKBUDGET_FUNDING_EXIT |
| --- | --- | --- |
| 2022 | -0.1574 | -0.1348 |
| 2023 | 2.0114 | 2.0410 |
| 2024 | 0.9461 | 0.9935 |
| 2025 | 1.1235 | 1.1977 |
| 2026 | 1.0360 | 1.0720 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | H5_BASELINE | -0.1574 |
| 1 | LS9_H5_RISKBUDGET_FUNDING_EXIT | -0.1348 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 2,022.0000 | 1,359.0000 | 25.3369 | 2.0680 |
| 1 | H5_BASELINE | 2,023.0000 | 1,359.0000 | 7.0894 | 1.5419 |
| 2 | H5_BASELINE | 2,024.0000 | 1,358.0000 | 10.9698 | 1.7981 |
| 3 | H5_BASELINE | 2,025.0000 | 1,359.0000 | 10.0538 | 1.6957 |
| 4 | H5_BASELINE | 2,026.0000 | 1,461.0000 | 10.4858 | 1.5638 |
| 5 | LS9_H5_RISKBUDGET_FUNDING_EXIT | 2,022.0000 | 1,359.0000 | 27.6053 | 2.1245 |
| 6 | LS9_H5_RISKBUDGET_FUNDING_EXIT | 2,023.0000 | 1,359.0000 | 7.8537 | 1.6159 |
| 7 | LS9_H5_RISKBUDGET_FUNDING_EXIT | 2,024.0000 | 1,358.0000 | 11.9807 | 1.8635 |
| 8 | LS9_H5_RISKBUDGET_FUNDING_EXIT | 2,025.0000 | 1,359.0000 | 10.8672 | 1.7536 |
| 9 | LS9_H5_RISKBUDGET_FUNDING_EXIT | 2,026.0000 | 1,461.0000 | 11.5267 | 1.6242 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 365.0000 | 2022-05-12 | 2.1634 | 0.7970 |
| 1 | LS9_H5_RISKBUDGET_FUNDING_EXIT | 365.0000 | 2022-05-12 | 2.2367 | 0.7865 |
