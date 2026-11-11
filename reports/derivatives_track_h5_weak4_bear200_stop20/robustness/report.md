# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | H5_BASELINE | LS11_H5_WEAK4_BEAR200_STOP20 |
| --- | --- | --- |
| 2022 | -0.1961 | 0.0684 |
| 2023 | 2.7720 | 2.5285 |
| 2024 | 1.1925 | 0.9874 |
| 2025 | 1.5102 | 1.6204 |
| 2026 | 1.4101 | 1.5364 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | H5_BASELINE | -0.1961 |
| 1 | LS11_H5_WEAK4_BEAR200_STOP20 | 0.0684 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 2,022.0000 | 1,359.0000 | 50.0330 | 2.0657 |
| 1 | H5_BASELINE | 2,023.0000 | 1,359.0000 | 10.6628 | 1.5431 |
| 2 | H5_BASELINE | 2,024.0000 | 1,358.0000 | 18.3441 | 1.7969 |
| 3 | H5_BASELINE | 2,025.0000 | 1,359.0000 | 16.0225 | 1.6888 |
| 4 | H5_BASELINE | 2,026.0000 | 1,461.0000 | 16.6884 | 1.5578 |
| 5 | LS11_H5_WEAK4_BEAR200_STOP20 | 2,022.0000 | 1,359.0000 | 46.6087 | 2.0284 |
| 6 | LS11_H5_WEAK4_BEAR200_STOP20 | 2,023.0000 | 1,359.0000 | 14.1121 | 1.6774 |
| 7 | LS11_H5_WEAK4_BEAR200_STOP20 | 2,024.0000 | 1,358.0000 | 25.0554 | 1.9489 |
| 8 | LS11_H5_WEAK4_BEAR200_STOP20 | 2,025.0000 | 1,359.0000 | 19.0027 | 1.7672 |
| 9 | LS11_H5_WEAK4_BEAR200_STOP20 | 2,026.0000 | 1,461.0000 | 19.6325 | 1.6228 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | H5_BASELINE | 365.0000 | 2022-05-12 | 2.5547 | 0.7325 |
| 1 | LS11_H5_WEAK4_BEAR200_STOP20 | 365.0000 | 2022-06-23 | 2.5585 | 0.7735 |
