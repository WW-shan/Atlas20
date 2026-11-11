# H5 Exit + 14D Weak-Four Fixed-Risk Combo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement, preregister, and evaluate `PR2026-11-LS5-H5-EXIT-WEAK4-RISK05` without touching live H5 or routing orders.

**Architecture:** Add two pure signal builders: one emits the fixed-risk weekly weak-four short schedule, and one merges it with the existing H5-exit short schedule by asset-level maximum. A research-only runner combines the merged short schedule with H5 through the existing cash-budgeted gross allocator and the existing hourly isolated-margin engine.

**Tech Stack:** Python 3.11, pandas, numpy, pytest, existing Atlas20 derivative engine.

**Spec:** `docs/superpowers/specs/2026-11-11-h5-exit-weak4-risk-combo-design.md`

## Global Constraints

- Strict point-in-time CMC Top20 only.
- No leverage: H5 long 1.0x, target total gross 0.95, hard observed gross 1.00.
- Every short leg is 2.5% NAV; 20% adverse stop corresponds to nominal 0.5% NAV risk.
- Same asset under both sleeves gets one 2.5% leg, never 5%.
- Sleeve B uses 14D trailing return, bottom four, seven-day grid, R6 funding filter.
- Stopped sleeve-B legs do not reopen before the next weekly event.
- Costs: 2/20/50/100 bps.
- No parameter scan after seeing LS5 results.
- Do not stage live execution or OOS dirty files.

---

### Task 1: Build the weekly weak-four short schedule

**Files:**
- Modify: `src/atlas20/derivatives/signals.py`
- Test: `tests/test_derivatives_signals.py`

**Interfaces:**
- Consumes: `_ranked_weakest_top20(...)`, `funding_filter(...)`, `_as_utc(...)`, existing price and universe frames.
- Produces:
  `build_cross_sectional_weak_short_schedule(prices, universe, h5_targets, *, calendar, funding_rates, eligible, short_available, lookback=14, rebalance_days=7, short_count=4, per_asset_weight=0.025, funding_threshold=-0.0002, funding_lookback=3, anchor) -> dict[pd.Timestamp, pd.Series]`

- [x] **Step 1: Write the failing test**

```python
def test_weak_short_schedule_selects_bottom_four_on_fixed_weekly_grid() -> None:
    from atlas20.derivatives.signals import build_cross_sectional_weak_short_schedule

    dates = pd.date_range("2026-01-01", periods=8, freq="D", tz="UTC")
    prices = pd.DataFrame(
        {
            "a": [100, 100, 100, 100, 100, 100, 100, 100],
            "b": [100, 101, 102, 103, 104, 105, 106, 107],
            "c": [100, 99, 98, 97, 96, 95, 94, 93],
            "d": [100, 98, 96, 94, 92, 90, 88, 86],
            "e": [100, 97, 94, 91, 88, 85, 82, 79],
            "f": [100, 96, 92, 88, 84, 80, 76, 72],
        },
        index=dates,
    )
    universe = pd.DataFrame(
        {"rebalance_date": [dates[0]] * 6, "coin_id": list(prices.columns)}
    )
    h5 = {dates[0]: pd.Series({"a": 0.5})}
    funding = pd.DataFrame(0.0, index=[dates[0]], columns=prices.columns)

    schedule = build_cross_sectional_weak_short_schedule(
        prices,
        universe,
        h5,
        calendar=dates,
        funding_rates=funding,
        eligible=set(prices.columns),
        short_available=lambda asset, date: True,
        anchor=dates[0],
    )

    assert sorted(schedule) == [dates[0], dates[7]]
    assert set(schedule[dates[0]].index) == {"c", "d", "e", "f"}
    assert schedule[dates[0]].sum() == pytest.approx(0.10)
    assert "a" not in schedule[dates[0]].index
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_derivatives_signals.py::test_weak_short_schedule_selects_bottom_four_on_fixed_weekly_grid -q`

Expected: FAIL because `build_cross_sectional_weak_short_schedule` is not defined.

- [x] **Step 3: Implement the minimal schedule**

Add a function that normalizes UTC dates, emits targets only on the fixed seven-day grid, forward-fills H5 holdings, excludes those holdings, ranks 14D trailing returns, filters unavailable/funding-failing assets, and assigns `per_asset_weight` per selected asset.

- [x] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_derivatives_signals.py::test_weak_short_schedule_selects_bottom_four_on_fixed_weekly_grid -q`

Expected: PASS.

- [x] **Step 5: Add a failing funding-fail-closed test**

```python
def test_weak_short_schedule_excludes_missing_funding() -> None:
    from atlas20.derivatives.signals import build_cross_sectional_weak_short_schedule

    dates = pd.date_range("2026-01-01", periods=8, freq="D", tz="UTC")
    prices = pd.DataFrame(
        {name: [100 - i for i in range(8)] for name in ["a", "b", "c", "d", "e"]},
        index=dates,
    )
    prices["e"] = range(100, 92, -1)
    universe = pd.DataFrame(
        {"rebalance_date": [dates[0]] * 5, "coin_id": list(prices.columns)}
    )
    funding = pd.DataFrame(
        {"a": [0.0], "b": [0.0], "c": [0.0], "d": [0.0]},
        index=[dates[0]],
    )

    schedule = build_cross_sectional_weak_short_schedule(
        prices,
        universe,
        {dates[0]: pd.Series({"a": 0.5})},
        calendar=dates,
        funding_rates=funding,
        eligible=set(prices.columns),
        short_available=lambda asset, date: True,
        anchor=dates[0],
    )

    assert "e" not in schedule[dates[0]].index
    assert len(schedule[dates[0]]) == 3
```

- [x] **Step 6: Run the new test to verify it fails, then make it pass**

Run the exact test, observe the missing-funding asset is currently included, add the `funding_filter` condition with `funding_lookback`, then rerun and observe PASS.

- [x] **Step 7: Commit**

```bash
git add src/atlas20/derivatives/signals.py tests/test_derivatives_signals.py
git commit -m "feat: add weekly weak-four short schedule"
```

---

### Task 2: Merge fixed-risk short sleeves without double sizing

**Files:**
- Modify: `src/atlas20/derivatives/signals.py`
- Test: `tests/test_derivatives_signals.py`

**Interfaces:**
- Consumes: mappings from timestamps to non-negative short weights.
- Produces:
  `combine_fixed_risk_short_schedules(schedules, *, per_asset_weight) -> dict[pd.Timestamp, pd.Series]`

- [x] **Step 1: Write the failing overlap test**

```python
def test_combine_fixed_risk_short_schedules_uses_max_not_sum() -> None:
    from atlas20.derivatives.signals import combine_fixed_risk_short_schedules

    d1 = pd.Timestamp("2026-01-01", tz="UTC")
    d2 = pd.Timestamp("2026-01-02", tz="UTC")
    combined = combine_fixed_risk_short_schedules(
        {
            "exit": {
                d1: pd.Series({"ethereum": 0.025, "solana": 0.025}),
                d2: pd.Series({"ethereum": 0.025}),
            },
            "weak": {d1: pd.Series({"ethereum": 0.025, "cardano": 0.025})},
        },
        per_asset_weight=0.025,
    )

    assert combined[d1]["ethereum"] == pytest.approx(0.025)
    assert combined[d1]["solana"] == pytest.approx(0.025)
    assert combined[d1]["cardano"] == pytest.approx(0.025)
    assert combined[d1].sum() == pytest.approx(0.075)
    assert set(combined[d2].index) == {"ethereum", "cardano"}
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_derivatives_signals.py::test_combine_fixed_risk_short_schedules_uses_max_not_sum -q`

Expected: FAIL because the function is not defined.

- [x] **Step 3: Implement forward-filled asset-level maximum**

Normalize each schedule, forward-fill sleeve states on the union event calendar, compute `max` across sleeve weights for each asset, enforce the per-asset cap, and emit only changed targets plus explicit empty close events.

- [x] **Step 4: Run test to verify it passes**

Run the exact test and observe PASS.

- [x] **Step 5: Add a failing explicit-close test**

```python
def test_combine_fixed_risk_short_schedules_emits_empty_close_event() -> None:
    from atlas20.derivatives.signals import combine_fixed_risk_short_schedules

    d1 = pd.Timestamp("2026-01-01", tz="UTC")
    d2 = pd.Timestamp("2026-01-02", tz="UTC")
    combined = combine_fixed_risk_short_schedules(
        {"exit": {d1: pd.Series({"ethereum": 0.025}), d2: pd.Series(dtype=float)}},
        per_asset_weight=0.025,
    )

    assert combined[d2].empty
```

- [x] **Step 6: Verify close-event behavior then commit**

Run the exact test; fix only if it fails for the missing empty close event, then run both signal tests.

```bash
git add src/atlas20/derivatives/signals.py tests/test_derivatives_signals.py
git commit -m "feat: merge fixed-risk short sleeves"
```

---

### Task 3: Add the research runner and manifest override

**Files:**
- Create: `scripts/run_h5_exit_weak_combo.py`
- Modify: `scripts/run_h5_exit_short.py`
- Create: `tests/test_run_h5_exit_weak_combo.py`
- Modify: `tests/test_run_h5_exit_short.py`

**Interfaces:**
- Consumes: the two signal builders from Tasks 1-2 and `_run_one(...)` from `scripts.run_h5_exit_short`.
- Produces: executable research runner with candidate ID `PR2026-11-LS5-H5-EXIT-WEAK4-RISK05`.

- [x] **Step 1: Write failing runner constant tests**

```python
def test_runner_freezes_combined_candidate() -> None:
    from scripts.run_h5_exit_weak_combo import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS5-H5-EXIT-WEAK4-RISK05"
    assert FROZEN_CONFIG["short_per_asset_weight"] == 0.025
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
    assert FROZEN_CONFIG["max_total_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.00
    assert FROZEN_CONFIG["cross_sectional_lookback"] == 14
    assert FROZEN_CONFIG["cross_sectional_rebalance_days"] == 7
    assert FROZEN_CONFIG["cross_sectional_short_count"] == 4
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_run_h5_exit_weak_combo.py -q`

Expected: collection failure because the runner does not exist.

- [x] **Step 3: Add construction-label regression test**

```python
def test_manifest_construction_override() -> None:
    from scripts.run_h5_exit_short import _manifest_construction

    class Args:
        construction = "H5 1.0x + exit + weak-four fixed-risk shorts"

    assert _manifest_construction(Args(), baseline=False) == Args.construction
    assert _manifest_construction(Args(), baseline=True) == "H5 1.0x"
```

Run it and observe failure before adding `_manifest_construction`.

- [x] **Step 4: Implement runner and manifest override**

The runner must:

1. reconstruct H5 with `build_trial(trial_by_id("PR2026-10-H5"), ...)`;
2. build eligible PIT membership and LS4 exit schedule;
3. build the weekly weak-four schedule;
4. merge both with `combine_fixed_risk_short_schedules`;
5. call `_run_one` with the frozen LS5 config and construction label;
6. write sleeve schedules and an audit file next to the run output.

- [x] **Step 5: Run signal and runner tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_derivatives_signals.py tests/test_run_h5_exit_short.py tests/test_run_h5_exit_weak_combo.py -q
```

Expected: all PASS.

- [x] **Step 6: Commit**

```bash
git add scripts/run_h5_exit_weak_combo.py scripts/run_h5_exit_short.py tests/test_run_h5_exit_short.py tests/test_run_h5_exit_weak_combo.py
git commit -m "feat: add combined fixed-risk short runner"
```

---

### Task 4: Preregister LS5 before any formal run

**Files:**
- Modify: `reports/research_trial_inventory/preregistered_trials.csv`

**Interfaces:**
- Consumes: frozen spec and runner constants.
- Produces: exactly one `registered` row for LS5 with hashes.

- [x] **Step 1: Build the registration row**

Use `scripts.run_phase_momentum_hypotheses.ledger_registration_row` semantics. The `spec` JSON must include all frozen values from the design.

- [x] **Step 2: Append only one registration row**

```bash
.venv/bin/python <one-off preregistration command>
```

- [x] **Step 3: Verify the row and hashes**

```bash
.venv/bin/python -m pytest tests/test_run_phase_momentum_hypotheses.py -q
```

Expected: PASS and no modification of the registration row afterward.

- [x] **Step 4: Commit**

```bash
git add reports/research_trial_inventory/preregistered_trials.csv
git commit -m "research: preregister LS5 combined short candidate"
```

---

### Task 5: Run the formal study

**Files:**
- Create: `reports/derivatives_track_h5_exit_weak4_risk/`

- [x] **Step 1: Run baseline and candidate at 20bps**

```bash
.venv/bin/python scripts/run_h5_exit_weak_combo.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_weak4_risk
.venv/bin/python scripts/run_h5_exit_weak_combo.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_weak4_risk
```

- [x] **Step 2: Run 2/50/100bps and 3x short-adverse funding**

Run both baseline and candidate at every cost and the candidate funding stress.

- [x] **Step 3: Run calendar, removal, rolling, saved-path starts and 12 real engine starts**

The 12 starts are 2022-01/05/09, 2023-01/05/09, 2024-01/05/09, 2025-01/05/09.

- [x] **Step 4: Run PBO/RC and both DSR scopes**

Use the inventory count after LS5 registration.

- [x] **Step 5: Compute short episodes and concentration**

Attribute each closed short to its originating sleeve. Overlap assets must not be counted twice.

---

### Task 6: Decide mechanically and write evidence

**Files:**
- Create: `reports/derivatives_track_h5_exit_weak4_risk/report.md`
- Create: `reports/derivatives_track_h5_exit_weak4_risk/manifest.json`
- Modify: `RESEARCH.md`
- Modify: `reports/research_trial_inventory/preregistered_trials.csv`

- [x] **Step 1: Apply every kill criterion without changing thresholds**

- [x] **Step 2: Write report and manifest**

Include realized adverse risk, gross breaches, cost/funding failures and true OOS boundary.

- [x] **Step 3: Append exactly one evaluated ledger row**

- [x] **Step 4: Update RESEARCH.md**

- [x] **Step 5: Run verification**

```bash
.venv/bin/python -m pytest tests/test_derivatives_engine.py \
  tests/test_derivatives_signals.py tests/test_run_h5_exit_short.py \
  tests/test_run_h5_exit_weak_combo.py tests/test_build_trial_inventory.py -q
make lint
make typecheck
git diff --check
```

- [x] **Step 6: Commit and push research evidence**

```bash
git add <explicit research files>
git commit -m "research: evaluate LS5 combined fixed-risk shorts"
git push origin research/long-short-cash-sleeve
```

---

### Task 7: Continue if LS5 rejects

**Files:**
- Create: a new spec and plan for the next mechanism.

- [x] **Step 1: Do not scan any LS5 parameter**
- [x] **Step 2: Identify the failed mechanism from the actual evidence**
- [x] **Step 3: Design a structurally different candidate**
- [x] **Step 4: Pre-register before running it**
