# Fixed-Strategy CSCV Stability

This test does not select the best in-sample parameter. It measures how often each fixed candidate ranks below the median out of sample across CSCV splits.

## Summary

| index | candidate | splits | test_percentile_median | test_percentile_mean | below_median_rate | train_percentile_median |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | parameter_ensemble_20bps | 924.0000 | 0.4375 | 0.4075 | 0.8571 | 0.4375 |
| 1 | primary | 924.0000 | 0.7812 | 0.7512 | 0.0747 | 0.7812 |
