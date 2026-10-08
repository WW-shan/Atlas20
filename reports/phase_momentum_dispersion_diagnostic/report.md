# Cross-sectional dispersion diagnostic

Book: `PR2026-10-H3` at 20 bps. Sample: 2022-01-01 .. 2026-09-21.

`top_minus_rest` is the mean forward return of the top dispersion bucket minus the day-weighted mean of the rest. The external mechanism predicts it is negative.

| index | measure | horizon_days | days | spearman_corr | top_bucket_forward_mean | rest_forward_mean | top_minus_rest | top_bucket_positive_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | trailing_21d | 1.0000 | 1,724.0000 | -0.0585 | 0.0014 | 0.0023 | -0.0009 | 0.3594 |
| 1 | trailing_21d | 5.0000 | 1,720.0000 | -0.1015 | 0.0025 | 0.0133 | -0.0108 | 0.3517 |
| 2 | trailing_21d | 21.0000 | 1,704.0000 | -0.1959 | -0.0017 | 0.0611 | -0.0628 | 0.2815 |
| 3 | trailing_7d | 1.0000 | 1,724.0000 | -0.0551 | 0.0023 | 0.0021 | 0.0001 | 0.3217 |
| 4 | trailing_7d | 5.0000 | 1,720.0000 | -0.0898 | 0.0094 | 0.0116 | -0.0021 | 0.3285 |
| 5 | trailing_7d | 21.0000 | 1,704.0000 | -0.1612 | 0.0126 | 0.0575 | -0.0450 | 0.2903 |
| 6 | daily | 1.0000 | 1,724.0000 | -0.0037 | 0.0023 | 0.0021 | 0.0002 | 0.2580 |
| 7 | daily | 5.0000 | 1,720.0000 | -0.0515 | 0.0111 | 0.0111 | -0.0000 | 0.2791 |
| 8 | daily | 21.0000 | 1,704.0000 | -0.1526 | 0.0190 | 0.0559 | -0.0370 | 0.2375 |
