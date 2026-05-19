# Review

## Claude

- Critical: none.
- Warning: none.
- Info: validation is intentionally fail-fast and the worker will rebuild the config; new service test duplicates config fixture data; cached Settings mutation is acceptable in current tests; adapter error text exposes `project_root` if this API becomes hosted.
- Result: approved.

## Gemini

- Not run: `codeagent-wrapper.exe --backend gemini` failed because `gemini` is not installed in PATH.

## Validation

- `python -m pytest tests/test_api_routes.py::test_backtests_run_endpoint_registers_queued_run tests/test_api_routes.py::test_backtests_run_endpoint_returns_422_when_base_yaml_missing tests/test_api_services.py::test_register_new_backtest_raises_when_base_yaml_missing -q` -> 3 passed.
- `python -m pytest tests/ -x -q` -> 168 passed.
- `cd apps/web && npm run test -- --run` -> 122 passed.
- `cd apps/web && npm run lint` -> passed.
- `cd apps/web && npm run typecheck` -> passed.
