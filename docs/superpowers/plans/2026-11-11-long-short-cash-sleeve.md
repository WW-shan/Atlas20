# Long-Short Cash Sleeve Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and run the pre-registered `PR2026-11-LS1-H5-H4-SECTOR20` research candidate without touching the live H5 or derivatives executor.

**Architecture:** Add one pure signed-sleeve composition helper to the derivatives signal layer, one research-only runner that constructs frozen H5/H4/sector targets and invokes the existing isolated-margin engine, and one append-only pre-registration ledger entry. The candidate and its same-engine H5 baseline are evaluated at 2/20/50/100 bps plus 3x short-adverse funding.

**Tech Stack:** Python 3.11, pandas, pytest, existing Atlas20 phase-momentum builders, existing Bitget mark and isolated-margin backtest engine.

**Spec:** `docs/superpowers/specs/2026-11-11-long-short-cash-sleeve-design.md`

## Global Constraints

- Strict point-in-time CMC Top20 only.
- H5 is frozen at 1.0x; no H5 1.25x/1.5x/2.0x in this candidate.
- H4 multiplier is exactly 0.2; sector short multiplier is exactly 0.2.
- Target gross is exactly 0.95; observed gross above 1.00 fails the trial.
- Costs are exactly 2/20/50/100 bps; no cost-dependent rule changes.
- `long_buffer=0.75`, `short_buffer=0.50`, `short_stop_loss_pct=0.20`, `max_margin_utilization=0.85`.
- No short-weight, H4-weight, stop, buffer, Top20, or funding-threshold scan.
- No live executor, plist, systemd, order-router, or H5 ledger change.
- No claim of live readiness before exact Bitget funding and 12 months OOS.

---

### Task 1: Add signed sleeve composition

**Files:**
- Modify: `src/atlas20/derivatives/signals.py`
- Test: `tests/test_derivatives_signals.py`

**Interfaces:**
- Produces: `combine_sleeve_targets(sleeves, *, max_gross) -> dict[pd.Timestamp, pd.Series]`
- `sleeves` is `Mapping[str, tuple[Mapping[pd.Timestamp, pd.Series], float]]`; the float is a signed multiplier.

- [ ] **Step 1: Write the failing test**

```python
def test_combine_sleeve_targets_forward_fills_and_scales_all_sleeves() -> None:
    from atlas20.derivatives.signals import combine_sleeve_targets

    d1 = pd.Timestamp("2026-01-01", tz="UTC")
    d2 = pd.Timestamp("2026-01-02", tz="UTC")
    h5 = {d1: pd.Series({"bitcoin": 0.40})}
    h4 = {d1: pd.Series({"ethereum": 0.50})}
    short = {d2: pd.Series({"solana": 1.00})}

    combined = combine_sleeve_targets(
        {
            "h5": (h5, 1.0),
            "h4": (h4, 0.2),
            "sector_short": (short, -0.2),
        },
        max_gross=0.50,
    )

    assert combined[d1]["bitcoin"] == pytest.approx(0.40)
    assert combined[d1]["ethereum"] == pytest.approx(0.10)
    target = combined[d2]
    assert target["bitcoin"] == pytest.approx(0.40 * 0.50 / 0.70)
    assert target["ethereum"] == pytest.approx(0.10 * 0.50 / 0.70)
    assert target["solana"] == pytest.approx(-0.20 * 0.50 / 0.70)
    assert target.abs().sum() == pytest.approx(0.50)
```

- [ ] **Step 2: Run it and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_derivatives_signals.py::test_combine_sleeve_targets_forward_fills_and_scales_all_sleeves -q
```

Expected: FAIL with `ImportError` or `AttributeError` because `combine_sleeve_targets` is missing.

- [ ] **Step 3: Implement the minimal helper**

Add to `src/atlas20/derivatives/signals.py` before `build_derivative_targets`:

```python
def combine_sleeve_targets(
    sleeves: Mapping[str, tuple[Mapping[pd.Timestamp, pd.Series], float]],
    *,
    max_gross: float,
) -> dict[pd.Timestamp, pd.Series]:
    """Forward-fill signed sleeve targets and cap their combined gross exposure."""
    if not np.isfinite(max_gross) or max_gross <= 0.0:
        raise ValueError("max_gross must be positive and finite")
    if not sleeves:
        return {}

    schedules: dict[str, dict[pd.Timestamp, pd.Series]] = {}
    multipliers: dict[str, float] = {}
    event_dates: set[pd.Timestamp] = set()
    for name, (raw_schedule, multiplier) in sleeves.items():
        if not np.isfinite(multiplier):
            raise ValueError(f"{name}: multiplier must be finite")
        schedule: dict[pd.Timestamp, pd.Series] = {}
        for raw_date, raw_target in raw_schedule.items():
            date = _as_utc(raw_date)
            target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
            target.index = target.index.astype(str)
            if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
                raise ValueError(f"{name}: target weights must be finite")
            schedule[date] = target.astype(float)
            event_dates.add(date)
        schedules[name] = dict(sorted(schedule.items()))
        multipliers[name] = float(multiplier)

    dates = sorted(event_dates)
    if not dates:
        return {}
    states: dict[str, pd.Series] = {name: pd.Series(dtype=float) for name in schedules}
    cursors = {name: 0 for name in schedules}
    combined_targets: dict[pd.Timestamp, pd.Series] = {}
    for date in dates:
        union_index: pd.Index = pd.Index([], dtype=object)
        for name, schedule in schedules.items():
            schedule_dates = list(schedule)
            cursor = cursors[name]
            while cursor < len(schedule_dates) and schedule_dates[cursor] <= date:
                states[name] = schedule[schedule_dates[cursor]].copy()
                cursor += 1
            cursors[name] = cursor
            union_index = union_index.union(states[name].index)
        combined = pd.Series(0.0, index=union_index, dtype=float)
        for name in schedules:
            if states[name].empty:
                continue
            combined = combined.add(
                states[name].reindex(union_index).fillna(0.0) * multipliers[name],
                fill_value=0.0,
            )
        combined = combined[combined.abs() > 1e-15]
        gross = float(combined.abs().sum())
        if gross > max_gross:
            combined *= max_gross / gross
        combined_targets[date] = combined
    return combined_targets
```

Add `"combine_sleeve_targets"` to `__all__`.

- [ ] **Step 4: Run the focused test and the full signals file**

```bash
.venv/bin/python -m pytest tests/test_derivatives_signals.py -q
```

Expected: PASS with 0 failures.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/derivatives/signals.py tests/test_derivatives_signals.py
git commit -m "feat: combine signed derivative sleeve targets"
```

---

### Task 2: Add the frozen candidate builder

**Files:**
- Modify: `src/atlas20/derivatives/signals.py`
- Test: `tests/test_derivatives_signals.py`

**Interfaces:**
- Produces: `build_cash_sleeve_targets(h5_targets, h4_targets, sector_targets) -> dict[pd.Timestamp, pd.Series]`
- Frozen multipliers are 1.0, 0.2, -0.2; frozen max gross is 0.95.

- [ ] **Step 1: Write the failing test**

```python
def test_build_cash_sleeve_targets_uses_frozen_weights() -> None:
    from atlas20.derivatives.signals import build_cash_sleeve_targets

    date = pd.Timestamp("2026-01-01", tz="UTC")
    combined = build_cash_sleeve_targets(
        {date: pd.Series({"bitcoin": 0.30})},
        {date: pd.Series({"ethereum": 0.50})},
        {date: pd.Series({"solana": 1.00})},
    )

    target = combined[date]
    assert target["bitcoin"] == pytest.approx(0.30)
    assert target["ethereum"] == pytest.approx(0.10)
    assert target["solana"] == pytest.approx(-0.20)
    assert target.abs().sum() == pytest.approx(0.60)
```

- [ ] **Step 2: Run it and verify RED**

```bash
.venv/bin/python -m pytest tests/test_derivatives_signals.py::test_build_cash_sleeve_targets_uses_frozen_weights -q
```

Expected: FAIL because `build_cash_sleeve_targets` is missing.

- [ ] **Step 3: Implement the frozen wrapper**

```python
def build_cash_sleeve_targets(
    h5_targets: Mapping[pd.Timestamp, pd.Series],
    h4_targets: Mapping[pd.Timestamp, pd.Series],
    sector_targets: Mapping[pd.Timestamp, pd.Series],
) -> dict[pd.Timestamp, pd.Series]:
    """Build the pre-registered H5+H4-minus-sector candidate target."""
    return combine_sleeve_targets(
        {
            "h5": (h5_targets, 1.0),
            "h4": (h4_targets, 0.2),
            "sector_short": (sector_targets, -0.2),
        },
        max_gross=0.95,
    )
```

Add `"build_cash_sleeve_targets"` to `__all__`.

- [ ] **Step 4: Run the focused tests**

```bash
.venv/bin/python -m pytest tests/test_derivatives_signals.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/derivatives/signals.py tests/test_derivatives_signals.py
git commit -m "feat: freeze long-short cash sleeve target"
```

---

### Task 3: Add the research-only runner

**Files:**
- Create: `scripts/run_long_short_cash_sleeve.py`
- Test: `tests/test_run_long_short_cash_sleeve.py`

**Interfaces:**
- CLI: `python scripts/run_long_short_cash_sleeve.py --cost-bps 20 --funding-source binance-proxy --funding-missing-policy skip`
- `--baseline` runs the same H5 1.0 target with no H4/short sleeve.
- Outputs `summary.json`, `daily_returns.csv`, `gross_exposure.csv`, `trades.csv`, `funding.csv`, `liquidations.csv`, `report.md`, `trial_results.csv`.

- [ ] **Step 1: Write the failing structural test**

```python
from scripts.run_long_short_cash_sleeve import CANDIDATE_ID, FROZEN_CONFIG


def test_runner_freezes_candidate_constants() -> None:
    assert CANDIDATE_ID == "PR2026-11-LS1-H5-H4-SECTOR20"
    assert FROZEN_CONFIG["h4_weight"] == 0.2
    assert FROZEN_CONFIG["sector_short_weight"] == 0.2
    assert FROZEN_CONFIG["max_gross"] == 0.95
    assert FROZEN_CONFIG["long_buffer"] == 0.75
    assert FROZEN_CONFIG["short_buffer"] == 0.50
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
```

- [ ] **Step 2: Run it and verify RED**

```bash
.venv/bin/python -m pytest tests/test_run_long_short_cash_sleeve.py::test_runner_freezes_candidate_constants -q
```

Expected: FAIL because the runner module does not exist.

- [ ] **Step 3: Implement the runner**

Create `scripts/run_long_short_cash_sleeve.py` with:

```python
CANDIDATE_ID = "PR2026-11-LS1-H5-H4-SECTOR20"
BASELINE_ID = "PR2026-11-LS1-H5-BASELINE"
FROZEN_CONFIG = {
    "h4_weight": 0.2,
    "sector_short_weight": 0.2,
    "max_gross": 0.95,
    "hard_gross": 1.0,
    "long_buffer": 0.75,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
}
```

Implement `_build_sector_targets` by importing `BaseSpec`, `build_base_targets`,
`build_regime_frame`, `absolute_trend_mask`, and `apply_daily_asset_stop_overlay`;
use `BaseSpec("SECTOR_LEAD_top2", "sector_lead", "sector_lead", "14D", "bull_only", top_n=2, concentrated=True)`
and asset MA50. Use existing `_load_market`, `_restrict_targets`, `_has_execution_mark`,
`load_mark_candles`, `load_binance_funding`, `run_derivative_backtest`, and
`_metrics_from_returns`.

For candidate mode:

```python
targets = build_cash_sleeve_targets(h5_targets, h4_targets, sector_targets)
```

For baseline mode:

```python
targets = build_cash_sleeve_targets(h5_targets, {}, {})
```

Use `max_gross_exposure=FROZEN_CONFIG["max_gross"]`, `long_buffer=0.75`,
`short_buffer=0.50`, `short_stop_loss_pct=0.20`, `funding_missing_policy` from CLI,
`missing_mark_policy="carry"`, and `missing_mark_max_carry_hours=3`.

Write `trial_results.csv` with `fill="lag0"`, `window="main"`, and the requested
`cost_bps` so the existing trial inventory can read the result path.

- [ ] **Step 4: Run the structural test and CLI help**

```bash
.venv/bin/python -m pytest tests/test_run_long_short_cash_sleeve.py -q
.venv/bin/python scripts/run_long_short_cash_sleeve.py --help
```

Expected: PASS and a non-empty help message.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_long_short_cash_sleeve.py tests/test_run_long_short_cash_sleeve.py
git commit -m "feat: add long-short cash sleeve research runner"
```

---

### Task 4: Register the candidate before running

**Files:**
- Modify: `reports/research_trial_inventory/preregistered_trials.csv`

- [ ] **Step 1: Append exactly one registration row**

Use `scripts.run_phase_momentum_hypotheses.append_ledger_rows` with:

```python
row = {
    "trial_id": "PR2026-11-LS1-H5-H4-SECTOR20",
    "hypothesis": "H5 untouched at 1.0x; H4 0.2x cash sleeve; failed sector leader strategy 0.2x short hedge",
    "role": "primary",
    "counts_as_trial": "True",
    "rule": "w = 1.0*w_H5 + 0.2*w_H4 - 0.2*w_SECTOR_LEAD_top2__asset_ma50; scale to target gross 0.95; hard observed gross 1.00; T+1 +3h; 20% short stop.",
    "kill_criterion": "20bps terminal > baseline; Sharpe > baseline; MDD <= baseline + 5pp; zero liquidations; max gross <= 1.00; 50bps and 100bps terminal > baseline; 100bps MDD <= 50%; 3x short-adverse funding zero liquidations and MDD <= 50%; remove-2022 and rolling-worst gates; PBO <= 0.50; single-step p <= 0.05; DSR >= 0.95 for promotion.",
    "spec": json.dumps({
        "track": "derivatives",
        "construction": "H5 1.0x + H4 0.2x - SECTOR_LEAD_top2__asset_ma50 0.2x",
        "main_window": ["2022-01-01", "2026-09-21"],
        "target_gross": 0.95,
        "hard_gross": 1.0,
        "h5_weight": 1.0,
        "h4_weight": 0.2,
        "sector_short_weight": 0.2,
        "long_buffer": 0.75,
        "short_buffer": 0.5,
        "short_stop_loss_pct": 0.2,
        "costs_bps": [2.0, 20.0, 50.0, 100.0],
    }, sort_keys=True, separators=(",", ":")),
    "parameters_sources": "docs/superpowers/specs/2026-11-11-long-short-cash-sleeve-design.md; H4/H5 registered trials; no_leverage_ablation_2022 negative-return diagnostic",
    "protocol": "Derivatives research only. Strict PIT Top20; Bitget mark; T+1 +3h; Binance funding proxy/skip in research; costs 2/20/50/100 bps.",
    "deviation_notes": "Exploratory target-gross=1.0 diagnostic motivated this trial but is not accepted as validation. No weight, stop, buffer, or funding-threshold scan is allowed after registration.",
    "registered_at_utc": "2026-11-11T00:00:00Z",
    "status": "registered",
    "recorded_at_utc": "2026-11-11T00:00:00Z",
    "result_path": "",
    "result": "",
}
```

Compute `spec_sha256` as SHA-256 of the canonical compact JSON, and
`registration_sha256` with the same `REGISTRATION_FIELDS` convention used by
`run_phase_momentum_hypotheses.ledger_registration_row`.

- [ ] **Step 2: Verify the ledger is append-only and readable**

```bash
.venv/bin/python -m pytest tests/test_build_trial_inventory.py -q
```

Expected: PASS; the new registration counts as an unscored derivative trial until a result row is appended.

- [ ] **Step 3: Commit the registration before any result exists**

```bash
git add reports/research_trial_inventory/preregistered_trials.csv
git commit -m "research: preregister long-short cash sleeve candidate"
```

---

### Task 5: Run the formal candidate and baseline

**Files:**
- Create: `reports/derivatives_track_long_short_cash_sleeve/**`

- [ ] **Step 1: Run baseline at 20bps**

```bash
.venv/bin/python scripts/run_long_short_cash_sleeve.py \
  --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_long_short_cash_sleeve
```

- [ ] **Step 2: Run candidate at 20bps**

```bash
.venv/bin/python scripts/run_long_short_cash_sleeve.py \
  --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_long_short_cash_sleeve
```

- [ ] **Step 3: Read the actual result and do not interpret a failed gate as a pass**

Compare `multiple`, `sharpe`, `max_drawdown`, `liquidation_count`,
`max_gross_exposure`, stop count, fees, and funding totals. If 20bps fails
`max_gross_exposure <= 1.00` or any kill criterion, record `rejected` and
still complete the cost/funding runs for the research record.

- [ ] **Step 4: Run cost and funding stress**

```bash
for cost in 2 50 100; do
  .venv/bin/python scripts/run_long_short_cash_sleeve.py \
    --cost-bps "$cost" \
    --funding-source binance-proxy --funding-missing-policy skip \
    --output-dir reports/derivatives_track_long_short_cash_sleeve
done
.venv/bin/python scripts/run_long_short_cash_sleeve.py \
  --cost-bps 20 --funding-source binance-proxy \
  --funding-missing-policy skip --funding-stress short-adverse \
  --funding-multiplier 3 \
  --output-dir reports/derivatives_track_long_short_cash_sleeve
```

- [ ] **Step 5: Commit raw results**

```bash
git add reports/derivatives_track_long_short_cash_sleeve
git commit -m "research: evaluate long-short cash sleeve candidate"
```

---

### Task 6: Add report, robustness checks, and ledger result

**Files:**
- Create: `reports/derivatives_track_long_short_cash_sleeve/report.md`
- Create: `reports/derivatives_track_long_short_cash_sleeve/manifest.json`
- Modify: `RESEARCH.md`
- Modify: `reports/research_trial_inventory/preregistered_trials.csv`

- [ ] **Step 1: Compute yearly, best-year removal, rolling 365-day worst, and start-phase metrics**

Use the saved daily returns and existing `_metrics_from_returns` and
`_rolling_worst`. Report every failure explicitly. Do not remove a failed gate.

- [ ] **Step 2: Compute multiple-testing diagnostics**

Use the existing stationary-bootstrap/PBO/DSR utilities. Report the new N
including this registered trial. A DSR below 0.95 must remain `provisional`.

- [ ] **Step 3: Write the final report and manifest**

The report must state:

- exact candidate and baseline numbers;
- all cost and funding runs;
- max observed gross and any >1.00 events;
- liquidation and stop counts;
- yearly returns and remove-2022 result;
- rolling worst;
- PBO/RC/DSR;
- whether the candidate is `rejected` or `provisional`;
- that live execution is not approved.

- [ ] **Step 4: Append the result row to the ledger**

Append a new row with `status="evaluated"`, `result_path` pointing to the
candidate's `trial_results.csv`, and a concise result string. Never modify the
registration row.

- [ ] **Step 5: Run full verification**

```bash
.venv/bin/python -m pytest tests/test_derivatives_signals.py tests/test_run_long_short_cash_sleeve.py tests/test_build_trial_inventory.py -q
make lint
make typecheck
git diff --check
```

Expected: all commands exit 0; if any fails, fix before claiming completion.

- [ ] **Step 6: Commit and push**

```bash
git add RESEARCH.md reports/derivatives_track_long_short_cash_sleeve \
  reports/research_trial_inventory/preregistered_trials.csv
git commit -m "research: close long-short cash sleeve evaluation"
git push -u origin research/long-short-cash-sleeve
```

---

## Self-review

- Every spec gate appears in Task 5 or Task 6.
- The candidate weights, target gross, hard gross, buffers, stop, costs, funding,
  and no-scan rule are fixed in Task 2 and the ledger.
- The live executor and H5 ledger are not modified.
- The runner cannot silently renormalize a missing sleeve; Task 3 uses existing
  fail-closed target restriction.
- The plan does not claim the pre-spec 26.41x diagnostic is a validation result.
