# SUPERSEDED — do not cite

Every number in this directory was produced before 2026-09-25 by code that
looked up the asset-trend filter by **column** instead of by row
(`asset_trend.get(signal_date, ...)` on a DataFrame). The lookup always
returned the empty default, so each trend-filter variant dropped its holding
every day and re-bought the current rank-1 coin, ignoring the Top2 hold rule
and the phase schedule. The filter logic was fixed in
`src/atlas20/strategies/phase_momentum.py` (row lookup, with a regression test
in `tests/test_phase_momentum.py`).

No script in the repository regenerates this directory. The corrected single
trend-filter variants are the `param_asset_trend_{50,100,150,200}` rows of
`reports/phase_momentum_2022/parameter_neighborhood.csv`; the corrected
combinations (`trend_100_trailing_stop_20`, `trend_100_target_vol_0.7`) are
columns of `reports/phase_momentum_multiple_testing_2022/candidate_returns.csv`,
built by `scripts/run_phase_momentum_candidates.py`.

| Variant @20 bps | Here (buggy) | Corrected (2026-09-25) |
|---|---:|---:|
| trend_50 | 17.57x | 24.39x |
| trend_100 | 14.71x | 16.70x |
| trend_150 | 10.68x | 17.03x |
| trend_200 | 10.57x | 11.13x |

The files are kept, unchanged, only as the audit trail that
`scripts/build_trial_inventory.py` counts.
