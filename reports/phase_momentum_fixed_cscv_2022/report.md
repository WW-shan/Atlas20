# Fixed-Candidate Half-Sample Rank Consistency

This is an in-sample diagnostic and is not out-of-sample evidence. CSCV
enumerates every half of the blocks, so each candidate's percentile over the
"test" halves is the same distribution as over the "training" halves. The
table shows how consistently each fixed candidate ranks within its own family
of 30 distinct candidates across half-samples. It cannot
correct for a candidate having been chosen with the full sample in view; see
the PBO, Deflated Sharpe and Reality Check in
`reports/phase_momentum_multiple_testing_2022/` for that.

## Summary

| index | candidate | splits | half_sample_percentile_median | half_sample_percentile_mean | below_median_rate |
| --- | --- | --- | --- | --- | --- |
| 0 | parameter_ensemble_20bps | 924.0000 | 0.3871 | 0.3908 | 0.8474 |
| 1 | primary | 924.0000 | 0.7419 | 0.7366 | 0.0206 |
