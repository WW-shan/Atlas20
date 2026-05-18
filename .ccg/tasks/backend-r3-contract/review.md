# Backend R3 Contract Review

## Files changed

- `src/atlas20/api/schemas.py` replaced with R3 Pydantic v2 schema models.
- `src/atlas20/api/mock_data.py` added frontend fallback mock constants.
- `src/atlas20/api/services.py` replaced with mock-backed service functions.
- `src/atlas20/api/routes/{overview,options,runs,backtests}.py` migrated to R3 routes.
- `src/atlas20/api/routes/{compare,universe,reports}.py` added.
- `src/atlas20/api/app.py` registers the new routers.
- `src/atlas20/api/runner.py` deleted as obsolete CSV/backtest execution path.
- `tests/test_api_routes.py` and `tests/test_api_services.py` rewritten.
- `tests/test_api_runner.py` deleted with the obsolete runner.

## Validation

- `python -m py_compile src/atlas20/api/schemas.py src/atlas20/api/mock_data.py` passed.
- `python -m py_compile` for app/services/routes passed.
- `pytest -q tests/test_api_routes.py tests/test_api_services.py` passed: 29 tests.
- `pytest -q` passed: 46 tests.
- Live uvicorn HTTP checks passed:
  - `/api/overview` -> `hero_kpi.ytdReturn = 12.4756`
  - `/api/runs/queue` -> length `6`
  - `/api/runs?page=1&pageSize=14&dateRange=all&q=&chips=&view=list` -> items length `14`
  - `/api/runs/btk_0142/detail` -> `kpi.sharpe = 3.42`
  - `/api/compare?ids=atlas,momentum,meanrev&range=YTD` -> `metrics.cagr.atlas = 1.584`
  - `/api/universe/alerts` -> length `6`
  - `/api/reports/digest/featured` -> `defaultFormat = markdown`

## External review

- Claude reviewer completed. No critical findings.
- Actionable findings fixed:
  - Non-canonical run detail no longer reuses canonical KPI data.
  - Added test coverage for family chips, combined chips, date-range cutoff behavior, and the aliased `rebalance.swaps[].in` wire key.
  - Hardened new backtest ID generation for empty mock lists.
  - Tightened refresh timestamp validation.
- Gemini reviewer could not run because `gemini` is not installed/on PATH for `codeagent-wrapper.exe`; the wrapper exited with `gemini command not found in PATH`.

## Deviations

- `/api/options` returns `{}` as allowed by the brief; the route file was updated even though it was not named in the explicit file list because the old `OptionsResponse` schema was removed.
- `/api/runs/{id}/detail` returns the canonical detail only for `btk_0142`; other run IDs return 404 rather than fabricating KPI data from the canonical run.
