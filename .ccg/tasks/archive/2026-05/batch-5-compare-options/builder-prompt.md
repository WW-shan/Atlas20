You are the codex builder for Atlas20 Batch 5.

Read the brief at `.ccg/tasks/batch-5-compare-options/brief.md` and implement
EVERYTHING in the "Scope" section.

Hard requirements:
1. Follow the Batch 3/4 data-access + fallback pattern. Refer to:
   - `src/atlas20/api/data_access/overview.py`
   - `src/atlas20/api/data_access/universe.py`
   - `src/atlas20/api/services.py` (look at `_load_overview_payload`)
2. New modules: `src/atlas20/api/data_access/compare.py` and
   `src/atlas20/api/data_access/options.py`. Optional: extract shared CSV
   helpers into `data_access/_common.py` IF they're used by 3+ modules
   already.
3. Add `OptionsPayload` + nested sub-models to `src/atlas20/api/schemas.py`.
4. Add `fallback_options` dict to `src/atlas20/api/mock_data.py`.
5. Refactor existing `get_compare()` body into `_get_compare_mock()` so the
   fallback path stays semantically identical to today. Wrap with try/except
   FileNotFoundError|ValueError as briefed.
6. Update `src/atlas20/api/routes/options.py` to return OptionsPayload.
7. Frontend: add `OptionsPayload` TypeScript interface to
   `apps/web/src/lib/api.ts` mirroring the Python schema; type the
   `getOptions()` return. Do NOT add new query hooks.
8. Tests must use `tmp_path` and synthetic CSVs — DO NOT depend on real
   `reports/latest/*.csv` or `data/processed/*.csv` (CI may not have them).
9. Final check: `python -m pytest tests/ -x -q` must show 109 passed
   (was 98 after Batch 4, +11 new tests).
10. Frontend type-check: `cd apps/web && npm run typecheck` must pass.
11. Stage and commit when green:
    `feat(api): R3/R9 real compare + options endpoints with mock fallback`

Report format at the end:
- ✅/❌ PASS or FAIL
- Files changed
- Test count delta (98 → ?)
- Frontend typecheck result
- Any deviations from brief
- Final commit hash

Apply your own internal review BEFORE the final commit (the same pattern
you used in Batch 4 — run gemini/claude review if available, otherwise just
self-check against the brief and apply fixes).
