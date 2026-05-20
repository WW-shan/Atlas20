ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 8 round-1 reviewer findings. Combined from Opus 4.7 (3 Info)
and codex (3 Warning + 3 Info). Each fix = separate commit. Run pytest after each.

## W1 — Costs validator error message lacks field name

File: `src/atlas20/api/schemas.py` around the BacktestConfig model_validator

**Current:** error like `"combined transaction costs must be ≤ 1000 bps"`

**Fix:** include explicit field names:
```python
if self.costs.feeBps + self.costs.slippageBps > 1000:
    raise ValueError("costs.feeBps + costs.slippageBps must be ≤ 1000")
```

Also check `slots ≤ topN` validator says `"allocation.slots must be ≤ universe.topN"`.

**Test:** add `test_validator_errors_include_field_names` in
`tests/test_backtest_config_validation.py`:
- Trigger costs > 1000 → assert ValidationError message contains "feeBps"
- Trigger slots > topN → assert message contains "slots" or "topN"

**Commit:** `fix(api): batch 8 reviewer pass — name offending fields in validation errors`

## W2 — project_root + base.yaml fragility

Files:
- `src/atlas20/api/settings.py:25` (`project_root` default)
- `src/atlas20/api/config_adapter.py:51` (base.yaml fallback)

**Current:** `project_root = Path.cwd()`. If API launched outside repo root,
config/ is missing. Same for missing base.yaml.

**Fix:**

1. In `settings.py`, change default to repo-root detection:
   ```python
   project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
   # api/settings.py → src/atlas20/api → src/atlas20 → src → repo root
   ```

2. In `config_adapter.py`, when both `config/{slug}.yaml` AND `config/base.yaml`
   are missing, raise `ValueError("base config 'config/base.yaml' not found at <project_root>")`.
   Do NOT synthesize a phantom config.

3. In `src/atlas20/api/routes/backtests.py`, wrap any adapter call in try/except:
   ```python
   try:
       research_config = to_research_config(config, settings)
   except ValueError as exc:
       raise HTTPException(status_code=422, detail=str(exc)) from exc
   ```
   (NOTE: adapter isn't called from the route YET — Batch 9 worker will call it.
    But add the try/except in `register_new_backtest` route as a forward guard.)

**Tests:**
- `test_settings_project_root_defaults_to_repo_root` — assert it ends with `Atlas20`
- `test_config_adapter_raises_when_base_yaml_missing` — point project_root at
  a tmp_path without config/, expect ValueError mentioning base.yaml

**Commit:** `fix(api): batch 8 reviewer pass — robust project_root + missing base.yaml ValueError`

## W3 — Toolbar list/grid toggle removed entirely

File: `apps/web/src/components/history/Toolbar.tsx`

**Current:** the list/grid view toggle UI was removed when C1 dropped the
backend param. But the UX feature (local-only toggle) should remain.

**Fix decision (Claude):** restore the toggle as **client-side-only state**.
Toggle controls how rows render in `RunHistoryTab` (list = table; grid =
card layout — pick a simple grid using existing card components).

Steps:
1. Add `viewMode` local state in `RunHistoryTab.tsx`: `useState<"list" | "grid">("list")`.
2. Restore the toggle buttons in `Toolbar.tsx` as a prop-controlled segmented
   control. Props: `viewMode: "list" | "grid"`, `onViewModeChange: (m) => void`.
3. In `RunHistoryTab`, conditionally render: `viewMode === "list"` → existing
   table; `viewMode === "grid"` → simple grid of cards (one card per RunRow
   with strategy + status pill + sharpe + sparkline placeholder).
4. **Do NOT send viewMode to the backend.**
5. Add `aria-label="View mode"` and `role="radiogroup"` on the toggle.

**Test in `RunHistoryTab.test.tsx`:**
- Render tab → click "Grid" toggle → assert grid layout test-id renders
- Click "List" → assert table renders again
- Assert no API call carries `view` param (check the query key or mock api.getRuns args)

**Commit:** `feat(ui): batch 8 reviewer pass — restore list/grid toggle as client-side state`

## Info — Boundary tests for Idempotency-Key

File: `tests/test_idempotency_route.py`

**Fix:** add 3 boundary tests:
- 64-char key (max valid) → 200 accepted
- 65-char key → 422 rejected
- `"!!!"` (special chars) → 422 rejected

**Commit:** `test(api): batch 8 reviewer pass — idempotency-key boundary regression`

## Info — ATLAS chip decoy test

File: `tests/test_api_services.py`

**Fix:** add a test asserting chip="ATLAS" does NOT match a strategy with
family="Other" but name="ATLAS_LIKE_DECOY". Requires extending mock data
or seeding via fixture.

**Commit:** `test(api): batch 8 reviewer pass — ATLAS chip excludes non-family decoy`

## Info — `/api/runs` reject unknown query params

File: `src/atlas20/api/routes/runs.py`

**Fix decision:** make `HistoryFilter` strict (extra="forbid"). When the
client sends `?view=list`, return 422 instead of silently ignoring.

Change in `schemas.py`:
```python
class HistoryFilter(StrictApiModel):  # was ApiModel
    ...
```

Routes/services that use HistoryFilter accept the same dict-like construction,
so this should be additive. Verify no test relies on extra fields being ignored.

**Test:** `test_runs_route_rejects_unknown_query_param` — `GET /api/runs?view=list`
should return 422.

**Commit:** `fix(api): batch 8 reviewer pass — reject unknown query params on /runs`

## Info — Adapter slug edge case 500 → 422

Already covered in W2 fix above (try/except in route).

## Info — positionPct precision contract

File: `src/atlas20/api/config_adapter.py` — add docstring near positionPct mapping:

```python
# Note: positionPct is interpreted as percent → decimal via /100, with no
# rounding. For positionPct=33.33, max_weight_per_coin becomes 0.3333.
# Downstream consumers should be precision-tolerant.
api_config.allocation.positionPct / 100,
```

**No test needed.**

**Commit:** `docs(api): batch 8 reviewer pass — document positionPct precision contract`

## Procedure

7 atomic commits in the order above. After EACH:
- `python -m pytest tests/ -x -q` green
- After W3 commit: `cd apps/web && npm run test -- --run` green
- After all done: full backend + frontend + lint + typecheck

## Report

- 7 commit hashes
- Final backend test count (159 → ~166)
- Final frontend test count (121 → ~123)
- Any deviations
</TASK>
