# Batch 2 Brief — Phase S1/O1/O2: Settings + Structured Logging + Request-ID

## Repo / branch
- `D:/Code/Atlas20`, branch `redesign/r3-premium`, HEAD `ee47675` (post Batch 1)
- Roadmap reference: `docs/redesign/ROADMAP.md` Phase S1, O1, O2

## Goal
Establish foundational backend infrastructure that every subsequent batch
depends on:
1. A single `Settings` source of truth read from env (pydantic-settings)
2. Structured JSON logging
3. Request-ID middleware so all logs from one HTTP request are correlatable

No business logic changes. CORS / paths / anchor_date / report_root that are
currently scattered should be moved into Settings but old defaults must be
preserved so all 52 existing tests keep passing without env changes.

## Files to create / change

### New: `src/atlas20/api/settings.py`
- Use `pydantic-settings` (`pip add pydantic-settings` — already in pyproject?
  if not, add to `[project.optional-dependencies] dev` and main deps)
- `class Settings(BaseSettings)`:
  - `env: Literal["dev", "test", "prod"] = "dev"`
  - `cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]`
  - `db_url: str = "sqlite:///./data/atlas20.sqlite"` (used by Phase P)
  - `secret_key: str = "dev-only-do-not-use-in-prod"`
  - `api_keys: set[str] = set()` (used by S4 later)
  - `enable_docs: bool = True`
  - `report_root: Path = Path("reports")`
  - `data_root: Path = Path("data")`
  - `anchor_date: date | None = None`  # used by services to override "today"
  - `log_level: Literal["DEBUG","INFO","WARNING","ERROR"] = "INFO"`
  - `log_format: Literal["json", "text"] = "json"`  # text only for local dev tail
- `model_config = SettingsConfigDict(env_prefix="ATLAS20_", env_file=".env", extra="ignore")`
- Expose a cached accessor `@lru_cache def get_settings() -> Settings`

### New: `apps/web/../../.env.example` — wait, that's frontend. For backend:
- Create root-level `.env.example` listing every Settings field with comment
- Add `.env` to `.gitignore` (verify; add if missing)

### Modify: `src/atlas20/api/app.py`
- Read settings via `get_settings()`
- CORS `allow_origins=settings.cors_origins`
- `docs_url=None if not settings.enable_docs else "/docs"`
- Same for `redoc_url` and `openapi_url`
- Mount middleware in this order: request-id → log → cors

### New: `src/atlas20/api/logging_config.py`
- `def configure_logging(settings: Settings) -> None`
- If `settings.log_format == "json"`: use `structlog` or `python-json-logger`
  to format as JSON with fields `{ts, level, logger, message, request_id?, ...extra}`
- If `text`: standard formatter for local dev
- Call from app factory on startup

### New: `src/atlas20/api/middleware/request_id.py`
- ASGI middleware (`BaseHTTPMiddleware` from starlette is fine)
- Read `X-Request-ID` from inbound headers; if absent generate `uuid.uuid4().hex`
- Attach to `request.state.request_id`
- Bind to log context using `structlog.contextvars.bind_contextvars(request_id=...)`
  so all log lines inside the request get the id automatically
- Set `X-Request-ID` on response
- Unbind on completion

### New: `src/atlas20/api/middleware/access_log.py`
- Log every request with `{method, path, status, duration_ms, request_id, client_ip}`
- Use `time.perf_counter_ns` for duration
- Exclude /healthz and /metrics from logs (those will exist soon)

### Modify: existing `src/atlas20/api/services.py`
- Replace hardcoded `ANCHOR_DATE = date(2026, 5, 19)` with:
  ```python
  def _today() -> date:
      from atlas20.api.settings import get_settings
      s = get_settings()
      if s.anchor_date is not None:
          return s.anchor_date
      return datetime.now(timezone.utc).date()
  ```
- Use `_today()` instead of `ANCHOR_DATE` in `_date_cutoff`
- Existing tests set anchor_date via env in conftest OR pass through —
  see "Tests" section below

### Add deps to `pyproject.toml`
- `pydantic-settings>=2.0`
- `python-json-logger>=2.0` OR `structlog>=24.0`
- (Choose one; `structlog` is more powerful but `python-json-logger` is simpler.
  Pick whichever is more idiomatic with FastAPI 0.116.)

## Tests

New file `tests/test_settings.py`:
- `Settings()` with no env reads defaults
- `Settings(cors_origins=["https://example.com"])` works
- `ATLAS20_LOG_LEVEL=DEBUG` env var overrides
- `Settings(anchor_date=date(2026, 5, 19))` works

New file `tests/test_request_id_middleware.py`:
- Client request without `X-Request-ID` header → response has uuid-shape id
- Client request with `X-Request-ID: foo-123` → response echoes `foo-123`
- Two requests get different generated ids (or same passed id)

New file `tests/test_logging.py`:
- After `configure_logging`, a logged line is valid JSON with required fields
- Capture output via `capsys` or `caplog`

New `tests/conftest.py` (if not exists) — set `ATLAS20_ANCHOR_DATE=2026-05-19`
so existing services tests that depend on a fixed date keep passing.

## Existing test compatibility
All 52 existing tests must still pass without modification. Concretely:
- `tests/test_api_services.py` tests that filter by dateRange depend on the
  current `ANCHOR_DATE = 2026-05-19`. After refactor, this becomes "today"
  unless env is set.
- Solution: in `conftest.py` set `ATLAS20_ANCHOR_DATE=2026-05-19` as a session
  fixture, OR use `monkeypatch.setenv` per test.

## Acceptance

1. `pytest -q tests/` — all 52 + new ~6 green
2. `python -c "from atlas20.api.settings import get_settings; s = get_settings(); print(s.cors_origins)"` — prints default list
3. `ATLAS20_ENV=prod ATLAS20_ENABLE_DOCS=false python -c "..."` — env override works
4. Start uvicorn, curl `/api/overview -H 'X-Request-ID: test-abc'` → response has same header echoed; logs contain JSON line with `request_id: "test-abc"`
5. Same curl WITHOUT header → response has uuid-shape id

## Commit
Single commit:
```
feat(api): S1/O1/O2 settings + JSON logging + request-id middleware
```

Body lists: new files, env vars exposed, conftest changes, test count.

## Out of scope (later batches)
- API key auth (S4) — only define the `api_keys` field, don't wire `Depends`
- Rate limit (S6)
- Metrics (O3)
- Health endpoint (O5) — separate
- DB / persistence (Phase P)

## After commit
Write `.ccg/tasks/batch-2-foundation/review.md` listing files, tests, manual
smoke results, any deviations.
