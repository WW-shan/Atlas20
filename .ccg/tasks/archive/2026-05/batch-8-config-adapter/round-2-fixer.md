ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply round-2 Warning fix on Atlas20 Batch 8.

## Warning — Adapter not wired into registration; route try/except is dead code

**Files:**
- `src/atlas20/api/services.py` (`register_new_backtest`)
- `src/atlas20/api/routes/backtests.py` (already has try/except → 422)
- `tests/test_api_routes.py` (add route-level 422 test)

**Current state:** `routes/backtests.py:31` catches `ValueError` around
`register_new_backtest(session, config)`, but `services.py:232`
(`register_new_backtest`) does NOT call `to_research_config()`. Result:
the route-level 422-on-bad-config guard is currently dead code.

**Fix decision (Claude):**

Wire `to_research_config` into `register_new_backtest` as a **validation
step** — call it BEFORE the DB insert, discard the result. Purpose:
fail fast at registration time if the BacktestConfig can't be adapted
(e.g., missing base.yaml, invalid preset slug). The actual execution by
Batch 9 worker will re-call the adapter, but failing here means the user
gets a 422 immediately instead of a "failed" run later.

```python
def register_new_backtest(session: Session, config: BacktestConfig) -> RunRowSummary:
    settings = get_settings()
    # Validate the config can be adapted before persisting the run.
    # Surfaces bad presets / missing base.yaml as ValueError, converted
    # to HTTP 422 by the route handler. The worker (Batch 9) re-runs the
    # adapter when executing; this is a fail-fast guard.
    to_research_config(config, settings)
    # ... existing logic to insert Run row ...
```

Import `to_research_config` from `atlas20.api.config_adapter`. Verify
import doesn't create a cycle (config_adapter imports settings; services
imports config_adapter; should be fine since settings doesn't import
services or config_adapter).

**Tests:**

1. **Route-level 422 test** in `tests/test_api_routes.py`:
   - Monkeypatch `settings.project_root` to a `tmp_path` that has NO
     `config/` dir.
   - POST `/api/backtests/run` with a valid BacktestConfig.
   - Assert response status == 422 and "base.yaml" in `response.json()["detail"]`.

2. **Service-level test** in `tests/test_api_services.py`:
   - Same setup (tmp_path without config/).
   - Call `register_new_backtest(session, config)` directly.
   - Assert `ValueError` raised with "base.yaml" in message.

3. **Happy path regression:** verify the existing `test_register_new_backtest`
   still passes — the project_root default points at the real Atlas20 repo
   which has `config/base.yaml`, so registration should still work.

**Procedure:**

Single commit:
`fix(api): batch 8 round 2 — wire to_research_config into register_new_backtest as fail-fast validation`

After commit:
- `python -m pytest tests/ -x -q` — expect 166 + 2 new = 168 passed
- `cd apps/web && npm run test -- --run` — still 122
- Lint + typecheck unchanged

## Report

- Commit hash
- Final backend test count
- Any deviations
</TASK>
