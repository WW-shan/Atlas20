# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | L125_BASELINE | LS22_H5_EXTREME_RUN_PROFIT_LOCK |
| --- | --- | --- |
| 2022 | -0.1961 | -0.1188 |
| 2023 | 2.7720 | 2.9241 |
| 2024 | 1.1925 | 0.9609 |
| 2025 | 1.5102 | 1.7280 |
| 2026 | 1.4101 | 1.4143 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | L125_BASELINE | -0.1961 |
| 1 | LS22_H5_EXTREME_RUN_PROFIT_LOCK | -0.1188 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | L125_BASELINE | 2,022.0000 | 1,359.0000 | 50.0330 | 2.0657 |
| 1 | L125_BASELINE | 2,023.0000 | 1,359.0000 | 10.6628 | 1.5431 |
| 2 | L125_BASELINE | 2,024.0000 | 1,358.0000 | 18.3441 | 1.7969 |
| 3 | L125_BASELINE | 2,025.0000 | 1,359.0000 | 16.0225 | 1.6888 |
| 4 | L125_BASELINE | 2,026.0000 | 1,461.0000 | 16.6884 | 1.5578 |
| 5 | LS22_H5_EXTREME_RUN_PROFIT_LOCK | 2,022.0000 | 1,359.0000 | 50.6795 | 2.1271 |
| 6 | LS22_H5_EXTREME_RUN_PROFIT_LOCK | 2,023.0000 | 1,359.0000 | 11.3810 | 1.6355 |
| 7 | LS22_H5_EXTREME_RUN_PROFIT_LOCK | 2,024.0000 | 1,358.0000 | 22.7755 | 1.9488 |
| 8 | LS22_H5_EXTREME_RUN_PROFIT_LOCK | 2,025.0000 | 1,359.0000 | 16.3711 | 1.7614 |
| 9 | LS22_H5_EXTREME_RUN_PROFIT_LOCK | 2,026.0000 | 1,461.0000 | 18.4988 | 1.6473 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | L125_BASELINE | 365.0000 | 2022-05-12 | 2.5547 | 0.7325 |
| 1 | LS22_H5_EXTREME_RUN_PROFIT_LOCK | 365.0000 | 2022-05-12 | 2.6922 | 0.8134 |
