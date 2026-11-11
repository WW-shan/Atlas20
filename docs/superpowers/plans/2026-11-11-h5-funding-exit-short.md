# H5 Funding-Rank Exit Short Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement, preregister, and evaluate `PR2026-11-LS6-H5-FUNDING-EXIT-RISK05`.

**Architecture:** Extend the existing exit-short builder with an optional entry predicate, add a pure funding-percentile helper, and create a research-only runner that reuses the validated LS4 engine/output path.

**Tech Stack:** Python 3.11, pandas, numpy, pytest, existing Atlas20 derivative engine.

**Spec:** `docs/superpowers/specs/2026-11-11-h5-funding-rank-exit-short-design.md`

## Global Constraints

- Strict point-in-time CMC Top20 only.
- H5 long 1.0x, target total gross 0.95, hard observed gross 1.00.
- Each short leg 2.5% NAV, 20% stop.
- Funding rank: 7D mean, PIT Top20, minimum five assets, top third >= 2/3.
- Missing funding fails closed.
- Costs 2/20/50/100bps.
- No parameter scan after LS6 results.

---

### Task 1: Add funding-percentile predicate

**Files:**
- Modify: `src/atlas20/derivatives/signals.py`
- Test: `tests/test_derivatives_signals.py`

**Interfaces:**
- Produces:
  `funding_rank_percentile(funding_rates, universe, asset, *, as_of, eligible, lookback_days=7, min_assets=5) -> float | None`

- [ ] **Step 1: Write the failing test**

```python
def test_funding_rank_percentile_uses_pit_top20_cross_section() -> None:
    from atlas20.derivatives.signals import funding_rank_percentile

    date = pd.Timestamp("2026-01-10", tz="UTC")
    funding = pd.DataFrame(
        {"a": [0.0001], "b": [0.0002], "c": [0.0003], "d": [0.0004], "e": [0.0005]},
        index=[date],
    )
    universe = pd.DataFrame(
        {"rebalance_date": [date] * 5, "coin_id": list(funding.columns)}
    )

    rank = funding_rank_percentile(
        funding,
        universe,
        "e",
        as_of=date,
        eligible=set(funding.columns),
    )

    assert rank == pytest.approx(1.0)
```

- [ ] **Step 2: Run test to verify RED**

Run: `.venv/bin/python -m pytest tests/test_derivatives_signals.py::test_funding_rank_percentile_uses_pit_top20_cross_section -q`

Expected: ImportError because the function does not exist.

- [ ] **Step 3: Implement the minimal helper**

Normalize dates, restrict to PIT Top20 and eligible assets, compute the last-7-calendar-day mean per funding column, fail closed below `min_assets`, and return the asset's pandas percentile rank.

- [ ] **Step 4: Run GREEN and commit**

```bash
.venv/bin/python -m pytest tests/test_derivatives_signals.py::test_funding_rank_percentile_uses_pit_top20_cross_section -q
git add src/atlas20/derivatives/signals.py tests/test_derivatives_signals.py
git commit -m "feat: add funding rank percentile"
```

---

### Task 2: Add optional exit-entry predicate

**Files:**
- Modify: `src/atlas20/derivatives/signals.py`
- Test: `tests/test_derivatives_signals.py`

**Interfaces:**
- Modifies:
  `build_exit_short_schedule(...)`
- Adds optional argument:
  `entry_allowed: Callable[[str, pd.Timestamp], bool] | None = None`

- [ ] **Step 1: Write the failing test**

```python
def test_build_exit_short_schedule_applies_entry_predicate() -> None:
    from atlas20.derivatives.signals import build_exit_short_schedule

    d1 = pd.Timestamp("2026-01-01", tz="UTC")
    d2 = pd.Timestamp("2026-01-02", tz="UTC")
    h5 = {
        d1: pd.Series({"bitcoin": 0.5, "ethereum": 0.5}),
        d2: pd.Series({"bitcoin": 0.5}),
    }
    eligible = {d1: {"bitcoin", "ethereum"}, d2: {"bitcoin", "ethereum"}}

    short = build_exit_short_schedule(
        h5,
        holding_days=5,
        eligible_by_date=eligible,
        per_asset_weight=0.025,
        entry_allowed=lambda asset, date: False,
    )

    assert short[d2].empty
```

- [ ] **Step 2: Verify RED**

Run the exact test and observe that the function rejects the unknown argument.

- [ ] **Step 3: Implement predicate check before activation**

Call `entry_allowed(asset, date)` after PIT eligibility and before adding to `active`. Existing callers with no predicate behave exactly as before.

- [ ] **Step 4: Run all signal tests and commit**

```bash
.venv/bin/python -m pytest tests/test_derivatives_signals.py -q
git add src/atlas20/derivatives/signals.py tests/test_derivatives_signals.py
git commit -m "feat: filter exit shorts by entry signal"
```

---

### Task 3: Add LS6 runner

**Files:**
- Create: `scripts/run_h5_funding_exit_short.py`
- Create: `tests/test_run_h5_funding_exit_short.py`

**Interfaces:**
- Consumes: `funding_rank_percentile`, `build_exit_short_schedule`, `_run_one`.
- Produces: candidate ID `PR2026-11-LS6-H5-FUNDING-EXIT-RISK05`.

- [ ] **Step 1: Write the failing constants test**

```python
def test_runner_freezes_funding_exit_candidate() -> None:
    from scripts.run_h5_funding_exit_short import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS6-H5-FUNDING-EXIT-RISK05"
    assert FROZEN_CONFIG["funding_lookback_days"] == 7
    assert FROZEN_CONFIG["funding_rank_min"] == pytest.approx(2 / 3)
    assert FROZEN_CONFIG["funding_min_assets"] == 5
    assert FROZEN_CONFIG["short_per_asset_weight"] == 0.025
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
```

- [ ] **Step 2: Verify RED**

Run the new test; expect import failure.

- [ ] **Step 3: Implement runner**

Reuse the LS4 main/load path, pass an `entry_allowed` lambda using `funding_rank_percentile`, and label the construction correctly through `_manifest_construction`.

- [ ] **Step 4: Run runner tests and commit**

```bash
.venv/bin/python -m pytest tests/test_run_h5_funding_exit_short.py tests/test_run_h5_exit_short.py -q
git add scripts/run_h5_funding_exit_short.py tests/test_run_h5_funding_exit_short.py
git commit -m "feat: add funding-rank exit short runner"
```

---

### Task 4: Preregister before formal run

**Files:**
- Modify: `reports/research_trial_inventory/preregistered_trials.csv`

- [ ] **Step 1: Build the canonical spec JSON and hashes**
- [ ] **Step 2: Append exactly one registered row**
- [ ] **Step 3: Verify ledger tests**
- [ ] **Step 4: Commit registration**

```bash
git add reports/research_trial_inventory/preregistered_trials.csv
git commit -m "research: preregister LS6 funding-rank exit short"
```

---

### Task 5: Run and evaluate

- [ ] **Step 1: Run baseline and candidate at 20bps**
- [ ] **Step 2: Run 2/50/100bps and 3x short-adverse**
- [ ] **Step 3: Run annual, removal, rolling, saved-path starts and 12 engine starts**
- [ ] **Step 4: Run PBO/RC and both DSR scopes**
- [ ] **Step 5: Compute episode and concentration attribution**
- [ ] **Step 6: Apply all kill criteria mechanically**

Expected commands:

```bash
.venv/bin/python scripts/run_h5_funding_exit_short.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_exit_short
.venv/bin/python scripts/run_h5_funding_exit_short.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_exit_short
```

---

### Task 6: Evidence and continuation

- [ ] **Step 1: Write report and manifest**
- [ ] **Step 2: Append one evaluated ledger row**
- [ ] **Step 3: Update RESEARCH.md**
- [ ] **Step 4: Run tests, lint, typecheck, manifest verification**
- [ ] **Step 5: Commit and push**
- [ ] **Step 6: If rejected, design a new mechanism without scanning LS6**
