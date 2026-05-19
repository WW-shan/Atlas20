# Batch 5 Compare + Options Implementation Plan

## Goal

Wire compare and options endpoints to real CSV artifacts with mock fallback, while preserving the existing frontend contract and existing mock compare behavior.

## Steps

1. Add failing tests using `tmp_path` synthetic CSVs for compare data access, options data access, and service fallback behavior.
2. Add focused CSV data-access modules:
   - `src/atlas20/api/data_access/compare.py`
   - `src/atlas20/api/data_access/options.py`
3. Add `OptionsPayload` and nested schema models in `src/atlas20/api/schemas.py`.
4. Add `fallback_options` in `src/atlas20/api/mock_data.py`.
5. Wire services:
   - Import both data-access loaders.
   - Refactor the current `get_compare()` body into `_get_compare_mock()`.
   - Add try/fallback for compare and options.
6. Update `src/atlas20/api/routes/options.py` to return `OptionsPayload`.
7. Add `OptionsPayload` TypeScript types and type `getOptions()` in `apps/web/src/lib/api.ts`.
8. Run targeted tests, full backend tests, frontend typecheck, self/CCG review, then commit when green.
