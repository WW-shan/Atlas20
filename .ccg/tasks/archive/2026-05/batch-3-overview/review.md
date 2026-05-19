# Batch 3 Review

## Files changed
- `src/atlas20/api/data_access/overview.py`: added CSV-backed OverviewPayload adapter using `settings.report_root`, with mock-only fields explicitly retained for P2.
- `src/atlas20/api/services.py`: `get_overview` now prefers real CSV reports and falls back to mock data with a warning; `get_featured_digest` selects the newest markdown report and falls back consistently when markdown or CSVs are unavailable.
- `tests/test_overview_data_access.py`: covers schema validation, champion ranking, benchmark exclusion, YTD math, missing CSV, and empty CSV.
- `tests/test_services_overview_fallback.py`: covers real overview data and mock fallback for missing/malformed reports.
- `tests/test_featured_digest.py`: covers real digest metadata, missing markdown fallback, newest markdown selection, and malformed CSV fallback.
- `tests/test_api_routes.py`: isolates route tests to an empty report root so fallback assertions stay deterministic.

## Validation
- `pytest -q tests/` -> 87 passed.
- `python -c "from atlas20.api.services import get_overview; p = get_overview(); print(p.champion.strategy, p.hero_kpi.ytdReturn)"` -> `ETH_BH__bull_only 0.0`.
- `npm test --prefix apps/web -- --run` -> 106 passed. Vitest still emits the existing jsdom `window.open` not-implemented stderr in reports tests while passing.
- Live uvicorn curl `/api/overview` -> `status=200 champion=ETH_BH__bull_only ytd=0.0 topStrategies=3`.

## Review notes
- Claude reviewer reported no Critical issues. Major actionable feedback addressed: deterministic route fallback tests, BTC benchmark exclusion from champion ranking, and featured digest full fallback when CSVs degrade.
- Gemini review could not run because `gemini` is not installed in PATH for `codeagent-wrapper`; the wrapper returned `gemini command not found in PATH`.
- The 6-point monthly equity curve cap was kept because the Batch 3 brief explicitly requires `_build_equity_curve` to return the six most recent month-end points.
