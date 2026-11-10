# Derivatives Track Calendar Robustness

- sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily returns)
- candidates: 2

## Yearly returns

| year | PR2026-10-D-L125 | PR2026-11-RS6-X-WEAK4-STOP20 |
| --- | --- | --- |
| 2022 | -0.1961 | 0.0662 |
| 2023 | 2.7720 | 2.3641 |
| 2024 | 1.1925 | 1.0714 |
| 2025 | 1.5102 | 1.8320 |
| 2026 | 1.4101 | 1.4619 |

## Worst single year per candidate

| index | candidate | worst_year_return |
| --- | --- | --- |
| 0 | PR2026-10-D-L125 | -0.1961 |
| 1 | PR2026-11-RS6-X-WEAK4-STOP20 | 0.0662 |

## Best-year removal (terminal multiple after deleting each calendar year)

| index | candidate | removed_year | days | multiple | sharpe |
| --- | --- | --- | --- | --- | --- |
| 0 | PR2026-10-D-L125 | 2,022.0000 | 1,359.0000 | 50.0330 | 2.0657 |
| 1 | PR2026-10-D-L125 | 2,023.0000 | 1,359.0000 | 10.6628 | 1.5431 |
| 2 | PR2026-10-D-L125 | 2,024.0000 | 1,358.0000 | 18.3441 | 1.7969 |
| 3 | PR2026-10-D-L125 | 2,025.0000 | 1,359.0000 | 16.0225 | 1.6888 |
| 4 | PR2026-10-D-L125 | 2,026.0000 | 1,461.0000 | 16.6884 | 1.5578 |
| 5 | PR2026-11-RS6-X-WEAK4-STOP20 | 2,022.0000 | 1,359.0000 | 48.5848 | 2.1223 |
| 6 | PR2026-11-RS6-X-WEAK4-STOP20 | 2,023.0000 | 1,359.0000 | 15.3980 | 1.8031 |
| 7 | PR2026-11-RS6-X-WEAK4-STOP20 | 2,024.0000 | 1,358.0000 | 25.0076 | 2.0233 |
| 8 | PR2026-11-RS6-X-WEAK4-STOP20 | 2,025.0000 | 1,359.0000 | 18.2911 | 1.8045 |
| 9 | PR2026-11-RS6-X-WEAK4-STOP20 | 2,026.0000 | 1,461.0000 | 21.0415 | 1.7163 |

## 365-day rolling worst case

| index | candidate | window_days | worst_start | rolling_1y_median_multiple | rolling_1y_worst_multiple |
| --- | --- | --- | --- | --- | --- |
| 0 | PR2026-10-D-L125 | 365.0000 | 2022-05-12 | 2.5547 | 0.7325 |
| 1 | PR2026-11-RS6-X-WEAK4-STOP20 | 365.0000 | 2022-06-23 | 2.7421 | 0.7958 |
