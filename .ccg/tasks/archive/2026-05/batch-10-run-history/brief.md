# Batch 10 — R2 + C5 + U10/U11 stub

## Goal

Make Run History show REAL runs (DB-backed from Batches 7-9). Verify
favorite mutation hits DB (no longer mock). Wire `+ ADD STRATEGY` modal
to Compare. Stub `+ NEW REPORT` modal (real wiring deferred to Batch 12
since `/api/reports/generate` doesn't exist yet).

R7 (Data Sources real) + R10 (Universe Refresh real) explicitly deferred
to Batch 11 (depend on S2/S6 from security batch).

## Scope (~300 LOC + 12 tests)

### R2 — Run History real

Most of R2 is ALREADY done after Batches 7-9 (DB-backed RunsRepo). Verify:
- `services.list_runs` reads from RunsRepo (DB), not mock_data
- `services.get_run_detail` reads from RunsRepo + Reports table
- `mock_data.fallback_runs_list` only consulted by seed CLI

**Additional brief item — disk fallback when DB empty:**
If DB has zero rows AND `reports/app_runs/` exists with run dirs, fall back
to reading `reports/app_runs/*/manifest.json` to synthesize RunRow objects.
This makes the API survive a DB wipe without re-seeding.

Implement in `src/atlas20/api/services.py`:
```python
def list_runs(session: Session, ...) -> tuple[list[RunRow], int]:
    settings = get_settings()
    rows, total = RunsRepo(session).list(...)
    if total == 0:
        # Disk fallback — scan reports/app_runs/{run_id}/manifest.json
        disk_rows = _load_runs_from_disk(settings.report_root / "app_runs", **filter)
        if disk_rows:
            return disk_rows, len(disk_rows)
    return [RunRow.model_validate(r) for r in rows], total
```

`_load_runs_from_disk` reads each `manifest.json` (contains run_id,
strategy, metrics) — does NOT parse directory names. Returns a list of
RunRow-shaped dicts.

**Test:** in `tests/test_run_history_disk_fallback.py`:
- DB empty + `reports/app_runs/btk_0001/manifest.json` present → returns 1 row
- DB has rows + disk → uses DB only
- DB empty + no disk → returns empty list (NOT mock data)

### C5 — Favorite sync (verify)

After Batch 7, `toggle_run_favorite` writes to DB. The frontend's
`RunHistoryTab` and `BacktestStudioTab` both read from the same
`/api/runs` endpoint, so favorites are auto-synced.

**Verify** with a test in `tests/test_favorite_sync.py`:
- Toggle favorite via `POST /api/runs/{id}/favorite`
- Assert RunsRepo.get returns favorited=True
- Assert `/api/runs?chips=favorited` includes the run
- Assert backtest queue endpoint (`GET /api/runs/queue`) reflects the same state

No code change expected — if test fails, fix.

### U10 — `+ ADD STRATEGY` modal

**File:** `apps/web/src/features/compare/StrategyCompareTab.tsx`

**Current state:** Compare tab has a hardcoded strategy set or no add button.

**Decision (Claude):** add a modal triggered by `+ ADD STRATEGY` button.
Modal contents:
- Multi-select listbox of strategies pulled from `getOptions().presets`
- Search filter input on top
- Currently-selected strategies pre-checked
- "Add" button commits the selection
- "Cancel" closes modal

On commit:
- Update local URL state (e.g., `?ids=BTC_BH__always_on,ETH_BH__always_on`)
- Trigger compare query refetch with new ids
- Verify: new strategy appears as additional column in compare table

**Frontend pattern:** use existing `<Card>` overlay or a real `<Dialog>`.
Check `apps/web/src/components/ui/` — if `<Dialog>` exists, use it; else
build a simple modal with overlay + focus trap.

**Test:** in `StrategyCompareTab.test.tsx`:
- Click `+ ADD STRATEGY` → modal renders
- See list of strategies from mocked `getOptions`
- Select 2 → click Add → modal closes → compare table includes 2 new columns
- Cancel preserves prior state

### U11 — `+ NEW REPORT` modal STUB

**File:** `apps/web/src/features/reports/ReportsExportsTab.tsx`

**Current state:** likely a placeholder button.

**Decision (Claude):** create the modal UI with all controls but stub the
submission:
- Modal contents:
  - Report type radio: weekly / run / compare / universe
  - Format checkboxes: markdown / pdf / png / csv (multi-select)
  - Strategy select (if type=run or type=compare) — pulled from getOptions.presets
  - Notes textarea (optional)
- "Generate" button:
  - Calls `POST /api/reports/generate` (NEW endpoint — stub)
  - Stub backend returns 202 with `{job_id: "fake-job-001", queued: true}`
  - Frontend shows toast "Report queued for generation"
- Modal closes

**Backend stub:** in `src/atlas20/api/routes/reports.py`:
```python
@router.post("/generate", status_code=202)
def generate_report(req: GenerateReportRequest) -> dict[str, str]:
    # STUB — actual generation in Batch 12 (F1-F7)
    return {"job_id": "stub-job-001", "status": "queued",
            "note": "report generation stubbed until Batch 12"}
```

`GenerateReportRequest` in `schemas.py`:
```python
class GenerateReportRequest(StrictApiModel):
    type: Literal["weekly", "run", "compare", "universe"]
    formats: list[Literal["markdown", "pdf", "png", "csv"]] = Field(min_length=1)
    strategy: str | None = None
    notes: str | None = None
```

**Tests:**
- Backend: `POST /api/reports/generate` with valid body → 202 with job_id
- Backend: invalid body (empty formats) → 422
- Frontend: modal renders, submitting calls API, success shows toast

## Files expected

**Backend:**
- `src/atlas20/api/services.py` — add `_load_runs_from_disk` fallback
- `src/atlas20/api/routes/reports.py` — `POST /generate` stub
- `src/atlas20/api/schemas.py` — `GenerateReportRequest`
- `tests/test_run_history_disk_fallback.py` (NEW, 3 tests)
- `tests/test_favorite_sync.py` (NEW, 2 tests)
- `tests/test_generate_report_stub.py` (NEW, 3 tests)

**Frontend:**
- `apps/web/src/features/compare/StrategyCompareTab.tsx` — add Modal + ADD button
- `apps/web/src/features/compare/AddStrategyModal.tsx` (NEW)
- `apps/web/src/features/reports/ReportsExportsTab.tsx` — add Modal trigger
- `apps/web/src/features/reports/NewReportModal.tsx` (NEW)
- `apps/web/src/lib/api.ts` — add `generateReport()` function
- `apps/web/src/components/ui/Dialog.tsx` (NEW if not exists — simple overlay
  with focus trap + Escape close)
- Tests:
  - `apps/web/src/features/compare/StrategyCompareTab.test.tsx` — add 3 cases
  - `apps/web/src/features/reports/ReportsExportsTab.test.tsx` — add 3 cases
  - `apps/web/src/components/ui/Dialog.test.tsx` (NEW, 2 cases if new component)

Total: ~300 LOC frontend + ~150 LOC backend + ~250 LOC tests.

## Out of scope

- R7 Data Sources real → Batch 11
- R10 Universe Refresh real → Batch 11
- Actual report generation logic → Batch 12 (F1-F7)
- Bookmarkable URL state via useSearchParams — Batch 14 polish

## Acceptance

- `python -m pytest tests/ -q` → 211 + 8 = 219 passed
- `cd apps/web && npm run test -- --run` → 123 + 8 = 131 passed
- Lint + typecheck clean
- Manual smoke:
  1. Worker runs, completes a backtest → reappears in /api/runs from DB
  2. Click favorite in History → updates queue widget
  3. Click ADD STRATEGY → modal → select → table grows column
  4. Click NEW REPORT → modal → submit → toast "queued"
  5. Wipe DB → existing reports/app_runs/ → /api/runs returns disk-derived rows

## Determinism

- `_load_runs_from_disk` deterministic: sorts by manifest.json mtime DESC
- Stub report generator returns fixed job_id (suffix with timestamp via `_time.utc_now_iso()` if needed)
