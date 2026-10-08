# Research Trial Inventory

Every strategy configuration the project has backtested, built by
`scripts/build_trial_inventory.py`. The multiple-testing diagnostics read
`summary.json`; `trial_sharpes.csv` has one row per configuration and study
and `trial_inventory.csv` one row per study.

Built at commit `161ca2f` from 2 uncommitted source file(s): `reports/phase_momentum_hypotheses_2026_10/runs.csv`, `reports/research_trial_inventory/preregistered_trials.csv`. `manifest.json` records the SHA-256 of every source.

## Totals

| scope | trials | with Sharpe | distinct Sharpe values | mean Sharpe | std (annualized) | std (per day) |
| --- | --- | --- | --- | --- | --- | --- |
| all_trials | 14,126 | 14,111 | 8,942 | 0.7936 | 0.6519 | 0.03412 |
| top20_2022_trials | 6,132 | 6,117 | 3,820 | 0.4303 | 0.3144 | 0.01646 |

`top20_2022_trials` is the comparable pool for the phase-momentum champion: Top20,
start 2022-01-01, cost nearest 20 bps. Its 6,117 Sharpe ratios come from
3,820 distinct return streams; configurations inside one study
that happen to give identical returns (liquidity tiers that never bind, stops
that never fire) count separately. The `all_trials` Sharpe dispersion mixes
windows (the April 2022-11-21 studies have Sharpe ratios near 2), so the
multiple-testing script uses it only for the trial count.

## Conventions

- A configuration is one set of rules and parameters on one universe. Costs,
  rolling starts, phase offsets and sub-windows are multiplicity, not configurations.
- A study is one report directory. A configuration is new unless it reproduces,
  to 1e-9, the Sharpe of a configuration in an earlier-processed study on the same
  window start, universe and cost, or re-runs the same grid cell on another window
  or data panel (`duplicate_of` in `trial_sharpes.csv` names the earlier one).
- Processing is scope-first (Top20/2022 in research order, then Top50/2022, then
  other windows), so a configuration counts in the Top20/2022 scope whenever it
  was tested there.
- Each study is read at the cost nearest 20 bps at which all its configurations
  ran. `N bps` is fee plus slippage per unit of one-way turnover
  (`src/atlas20/backtest/engine.py`: `fee_rate * sum|dw|`).
- Sharpe ratios are the stored annualized values, sqrt(365) * mean / std with a
  zero risk-free rate. Most runners use ddof=0, some ddof=1 (a 0.03% difference
  over 1,725 days); no conversion is applied.
- Pure buy-and-hold benchmarks are not configurations. The 32 candidates in
  `phase_momentum_multiple_testing_2022/` re-list configurations counted in their
  own studies and are not counted again.

## By strategy family

| family | all_trials | top20_2022_trials |
| --- | --- | --- |
| benchmark_timing | 99 | 98 |
| bull_offense | 792 | 648 |
| ctrend_lite | 5241 | 3626 |
| leader_momentum | 5761 | 655 |
| phase_momentum | 73 | 71 |
| sector | 647 | 254 |
| topN_momentum | 73 | 60 |
| tsmom | 1440 | 720 |

## Caveats

- **Text only.** 11 configurations exist only as RESEARCH.md text:
  the momentum-event BTC-gate and target-volatility neighbourhood of section 0.7
  (no gate; MA50 confirm 1-3; MA100 confirm 1 and 3; MA200 confirm 1-3; 90%/100%
  target vol) and the section 2 trend-stop champion with BTC allowed in selection.
  4 momentum-event neighbours report multiples only. All count as
  trials without a Sharpe ratio.
- **Deleted from reports/.** The April profit-max and sector studies were deleted in
  `9d71d1e` and are read with `git show 9d71d1e^:...`: 4,712 configurations on
  2022-11-21 to 2026-04-21 (old panel), not mentioned in RESEARCH.md. The 11-day /
  2-day BTC gate reused by the later CTREND rules comes from this lane
  (`profit_max_refine/champion_*_stop11_confirm2`); its best Sharpe is 2.30 (`git:profit_max_refine`).
  The 144-cell bull-offense scan survives only at `5b37099`; its 108 levered
  cells are no longer in reports/.
- **Re-implemented pipeline strategies.** The no-leverage ablation re-implements 7
  pipeline bull-only strategies as `X_bull__none`. On the shared 2021-01-01 window
  4 reproduce the pipeline Sharpe exactly and count once; 3 (`TOP20_EQ__bull_only`, `TOP20_MOM_top6_monthly__bull_only`, `TOP20_SECTOR_top3_monthly__bull_only`) differ by 0.99 to 1.06 in Sharpe, so they are different return streams and count as separate trials.
- **Earlier hand count.** A first inventory (2026-09-24) gave 14,124 configurations
  overall. It counted every profit-max row as new, but 14 reproduce an earlier
  study's Sharpe exactly (2 profit_max_search rows re-list pipeline strategies
  as benchmarks; 12 profit_max_refine rows (focused_profit_search) re-run
  profit_max_search cells),
  and it merged the 3 differing re-implementations above by name. This build
  therefore counts 14 fewer and 3 more. The Top20/2022 scope is unaffected.
- **Not verifiable, not counted.** The deleted `scripts/run_profit_max_refine.py`
  defines its own grid, but its summary CSV was never committed; the committed
  refine CSVs came from other code. RESEARCH.md says it replaced earlier `/tmp`
  results that were not kept.
- **Phase momentum design.** No trials are recorded for how the phase-momentum
  design itself was chosen (4 signals, 3 phases, 3-day check, Top2 hold), so the
  phase-momentum count understates the search that produced it.
- **Inferred fields.** The overlay-sweep and CTREND-focus window ends and the
  old-panel screen end are inferred; the cost of `ensemble_ctrend_2022_top50` is not
  recorded (20 bps assumed); the April studies' cost is the 10 + 10 bps preset.
