# Batch 2 Foundation Review

## Files
- `.env.example`
- `.gitignore`
- `pyproject.toml`
- `src/atlas20/api/app.py`
- `src/atlas20/api/settings.py`
- `src/atlas20/api/logging_config.py`
- `src/atlas20/api/middleware/request_id.py`
- `src/atlas20/api/middleware/access_log.py`
- `src/atlas20/api/services.py`
- `tests/conftest.py`
- `tests/test_settings.py`
- `tests/test_request_id_middleware.py`
- `tests/test_logging.py`

## Validation
- `pytest -q tests/test_settings.py tests/test_request_id_middleware.py tests/test_logging.py tests/test_api_services.py tests/test_api_routes.py` -> 39 passed
- `pytest -q tests/` -> 68 passed
- `git diff --cached --check` -> passed
- `python -c "from atlas20.api.settings import get_settings; s = get_settings(); print(s.cors_origins)"` -> default CORS list printed
- `ATLAS20_ENV=prod ATLAS20_ENABLE_DOCS=false ... create_app()` -> docs, redoc, and OpenAPI URLs were `None`

## Manual Smoke
- Started uvicorn on a temporary localhost port.
- `GET /api/overview` with `X-Request-ID: test-abc` returned 200 and echoed `X-Request-ID: test-abc`.
- `GET /api/overview` without `X-Request-ID` returned 200 with a generated 32-character hex request id.
- Captured access log contained a JSON line with `request_id: "test-abc"`.

## External Review
- Claude reviewer ran against the staged diff.
- Gemini reviewer could not run because the `gemini` CLI is not installed on PATH.
- Fixed the in-scope finding for unvalidated inbound `X-Request-ID` values by adding strict validation and UUID fallback.
- Added coverage proving request IDs are written to access logs.

## Deviations
- Did not add production-only `secret_key` validation because the batch acceptance explicitly verifies `ATLAS20_ENV=prod ATLAS20_ENABLE_DOCS=false` without requiring a secret override, and secret hardening is listed for a later security phase.
- Did not touch frontend files.
