# Batch 8 — E1 BacktestConfig adapter + E7 resource validation + C1/C2

## Goal

Bridge the API `BacktestConfig` (Pydantic) to the engine's `ResearchConfig`
so Batch 9 worker can actually run real backtests. Add resource validation
+ idempotency. Clean up two long-pending contract items (C1, C2).

## Scope (~350 LOC + 25 tests)

### E1 — `BacktestConfig → ResearchConfig` adapter

**File:** `src/atlas20/api/config_adapter.py` (NEW)

**Function:** `to_research_config(api_config: BacktestConfig, preset: str, settings: Settings) -> ResearchConfig`

**Algorithm:**

1. **Load base config**: read `config/{preset_slug}.yaml` from project root.
   If file missing, fall back to `config/base.yaml`. Available presets:
   `base`, `bear_bottom_to_current_2022_11_21_2026_04_22`,
   `five_year_2020_2024`, `five_year_exact_2021_04_22_2026_04_22`.

2. **`preset_slug`**: normalize `api_config.preset` to a filesystem-safe
   slug (lowercase, alphanumeric+underscore). If the resulting filename
   doesn't exist, fall back to `base.yaml`.

3. **Override mapping** (apply after loading base):

   | API field | Engine field | Notes |
   |---|---|---|
   | `universe.topN` | `universe.universe_size` | int |
   | `universe.excludeStable` | `universe.stablecoin_ids` | If True, keep existing list; if False, set to `[]` |
   | `universe.excludeWrapped` | `universe.exclude_wrapped_assets` | bool |
   | `window.start` | `start_date` | format as `"YYYY-MM-DD"` |
   | `window.end` | `end_date` | format as `"YYYY-MM-DD"` |
   | `window.rebalance` ("Weekly"/"Biweekly"/"Monthly") | `rebalancing.frequencies` | Map: Weekly → `{"weekly": "7D"}`, Biweekly → `{"biweekly": "14D"}`, Monthly → `{"monthly": "month_end"}`. SINGLE-entry dict — overrides base. |
   | `allocation.positionPct` | `frictions.max_weight_per_coin` | divide by 100 (percent → decimal) |
   | `allocation.slots` | no direct mapping | validate in E7; stored in run.params JSON |
   | `costs.feeBps` | `frictions.fee_bps` | float |
   | `costs.slippageBps` | `frictions.slippage_bps` | float |

4. Set `project_root` to `settings.project_root` (add this Settings field
   defaulting to `Path.cwd()` if not present).

5. Return validated `ResearchConfig` instance.

**Error handling:** raise `ValueError` (will be caught by route handler and
converted to 422) for:
- Invalid preset slug (allow `base` only as fallback)
- Inconsistent rebalance frequency mapping
- YAML parse errors

### E7 — Resource validation + idempotency

**File:** extend `src/atlas20/api/schemas.py:BacktestConfig` validators.

**New validators on BacktestConfig** (model_validator after):

1. **Window span ≤ 10 years**:
   ```python
   if (self.window.end - self.window.start).days > 365 * 10:
       raise ValueError("window span must not exceed 10 years")
   ```

2. **End date not in future**:
   ```python
   if self.window.end > _today():  # via atlas20.api._time
       raise ValueError("end date must not be in the future")
   ```

3. **topN ≤ 50 and slots ≤ topN**: already partially via `Field(ge=1)`, add
   upper bounds:
   ```python
   # in BacktestUniverse:
   topN: int = Field(ge=1, le=50)
   # in BacktestConfig model_validator:
   if self.allocation.slots > self.universe.topN:
       raise ValueError("slots must be ≤ topN")
   ```

4. **feeBps + slippageBps ≤ 1000**:
   ```python
   if self.costs.feeBps + self.costs.slippageBps > 1000:
       raise ValueError("combined transaction costs must be ≤ 1000 bps")
   ```

**Idempotency-Key header on POST /backtests/run**:

- Route reads `Idempotency-Key` header (alphanumeric/dash/underscore, 8-64 chars).
- If present, check `IdempotencyRepo.get(key)`:
  - If exists AND not expired → return cached response.
  - Else: execute, then `IdempotencyRepo.store(key, "POST", "/backtests/run", json.dumps(response), ttl_seconds=86400)`.
- If absent: behave as today (no caching).
- Reject invalid Idempotency-Key with 422.

**Acceptance:**
- POST with `topN=100` → 422 with "topN" in error detail
- POST with `Idempotency-Key: abc123` twice within 24h → same response, second insert NOT executed
- POST with `Idempotency-Key: abc123` then 25h later → executes again

### C1 — Drop `view` parameter

**Files:**
- `src/atlas20/api/schemas.py:256` — remove `view` field from `HistoryFilter`
- `src/atlas20/api/services.py:148` — remove `view` param from `list_runs`
- `src/atlas20/api/routes/runs.py:26` — remove `view` query param
- `apps/web/src/lib/api.ts` — remove `view` from `getRuns` params type
- `apps/web/src/features/history/*.tsx` — remove any view-related toggle UI

`view: list/grid` was a frontend display-only concept that leaked into the
API. The frontend can still toggle list/grid using local state — it just
doesn't send `view` to the backend.

**Test:** update tests that pass `view` param to drop it. Add a route test
asserting `GET /runs?view=list` returns 422 (extra forbidden param) since
HistoryFilter is StrictApiModel — actually HistoryFilter is `ApiModel`
(populate_by_name=True). Verify if it'd accept unknowns; either way add
test that `view` is not in the response/request schema.

### C2 — Chip semantics alignment

**Current** (`services.py:_matches_chip`):
```python
def _matches_chip(row, chip):
    if chip == "favorited": return bool(row.get("favorited"))
    if chip in RUN_STATUS_CHIPS: return row["status"] == chip
    if chip in RUN_FAMILY_CHIPS: return row.get("strategy_family") == chip
    return chip in row["strategy"]  # substring fallback
```

The substring fallback is ambiguous — e.g. chip `"ATLAS"` matches both
`strategy_family == "ATLAS"` AND `"ATLAS" in strategy_name`.

**Decision (Claude):** chip is family OR strategy-substring **explicitly**,
not both. Spec:

- `favorited` → favorited check
- one of RUN_STATUS_CHIPS → status match
- one of RUN_FAMILY_CHIPS → family match ONLY
- anything else → strategy substring match

Currently when chip is `"ATLAS"`, both family AND substring match would
hit — that's fine, the explicit family branch wins. But the ambiguity is
that a custom string like "MOMENTUM_LEAD" also works via substring. Keep
this. Just ensure family chips short-circuit cleanly without falling
through to substring.

**Test:** add tests in `tests/test_api_services.py`:
- chip="ATLAS" returns only family=="ATLAS" rows
- chip="MOMENTUM_LEAD" returns rows whose strategy name contains it
- chip="favorited" returns only favorited rows
- chip="completed" returns only completed status

This is mostly a verification batch — the current code already does this
correctly. If tests pass without change, declare C2 already-satisfied and
just add the regression tests.

### Resource validation tests

Add `tests/test_backtest_config_validation.py`:
1. topN=100 → ValidationError, mentions topN
2. slots=10 with topN=5 → ValidationError, mentions slots/topN
3. window span=11years → ValidationError
4. end=2030-01-01 (future relative to anchor) → ValidationError
5. feeBps=600 + slippageBps=500 (sum=1100) → ValidationError
6. Valid config (all bounds satisfied) → no error
7. Adapter: valid config produces ResearchConfig with correct mappings
8. Adapter: missing preset YAML falls back to base
9. Adapter: positionPct=35.0 maps to max_weight_per_coin=0.35
10. Adapter: rebalance=Biweekly maps to frequencies={"biweekly": "14D"}

### Idempotency tests

Add `tests/test_idempotency_route.py`:
1. POST without header → 200 + run created
2. POST with header twice → 200 first time, 200 same response second time, runs_repo only inserted once
3. POST with invalid header (`!!!`) → 422
4. POST with header, wait 25h (mock _time), POST again → second insert happens

## Files expected

- `src/atlas20/api/config_adapter.py` — NEW (~120 LOC)
- `src/atlas20/api/schemas.py` — add validators, remove `view` (~30 LOC delta)
- `src/atlas20/api/services.py` — drop `view` param + add idempotency (~20 LOC delta)
- `src/atlas20/api/routes/runs.py` — drop `view` query (~5 LOC delta)
- `src/atlas20/api/routes/backtests.py` — read Idempotency-Key header (~30 LOC delta)
- `src/atlas20/api/settings.py` — add `project_root` (~3 LOC delta)
- `tests/test_config_adapter.py` — NEW (~120 LOC, ~10 tests)
- `tests/test_backtest_config_validation.py` — NEW (~100 LOC, ~7 tests)
- `tests/test_idempotency_route.py` — NEW (~80 LOC, ~4 tests)
- `tests/test_api_services.py` — add C2 regression tests (~30 LOC delta)
- `tests/test_api_routes.py` — drop view param tests, add idempotency
- `apps/web/src/lib/api.ts` — drop view from getRuns params (~5 LOC delta)
- `apps/web/src/features/history/*.tsx` — drop view UI if any (~10 LOC delta)

## Out of scope

- Actually executing the backtest (Batch 9 worker)
- Caching identical configs without explicit Idempotency-Key
- Real DB-driven Run History (Batch 10)

## Acceptance

- `python -m pytest tests/ -q` — green (~159 = 139 + 20 new)
- `cd apps/web && npm run test -- --run` — still 122 or 121 if grid toggle test removed
- `cd apps/web && npm run typecheck` clean, `npm run lint` clean
- Backend boots; POST /backtests/run with valid config returns queued summary
- POST /backtests/run with topN=100 returns 422 with topN in detail
- POST /backtests/run with same Idempotency-Key twice returns same run_id

## Determinism

`_today()` is the only date source. No `random`. ResearchConfig produced
is deterministic for a given (BacktestConfig, settings) pair.

## Implementation notes

- Use `atlas20.api._time.today()` for the future-date check, NOT
  `date.today()`.
- IdempotencyKey storage already exists from Batch 7 — just wire the route.
- The `view` removal is breaking for any external client — but we're MVP,
  no external clients yet.
