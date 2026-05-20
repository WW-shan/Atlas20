# Batch 11 — Security S2-S9 + R7/R10 + C3

## Goal

Production-readiness security hardening. CORS gating, API key auth, rate
limiting, path validation. Unblocks R7 (Data Sources real) and R10
(Universe Refresh real) which depend on auth+rate-limit infra.

## Scope (~500 LOC + 30 tests)

### S2 — CORS gated by env

**File:** `src/atlas20/api/app.py` + `settings.py`

**Current:** `app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, ...)`.
Default already from settings. Need explicit prod gate.

**Fix decisions (Claude):**
- Dev default `["http://localhost:5173", "http://127.0.0.1:5173"]`
- Prod: if `cors_origins` is empty AND `settings.env == "prod"` → raise
  `RuntimeError("ATLAS20_CORS_ORIGINS must be set in prod")` at startup
- Settings: validator on `cors_origins` enforces this

### S3 — Docs disabled in prod

**File:** `src/atlas20/api/app.py`

**Current:** `docs_url = "/docs" if settings.enable_docs else None`

**Fix:** force `enable_docs=False` when `settings.env == "prod"`, regardless
of explicit value. Settings post-init: `if env == "prod": enable_docs = False`.

Test: prod env + enable_docs=True → `/docs` returns 404.

### S4 — API Key auth (MVP)

**New file:** `src/atlas20/api/dependencies/auth.py`

```python
from fastapi import Header, HTTPException
from atlas20.api.settings import get_settings

def verify_api_key(x_api_key: str = Header(None)) -> str:
    settings = get_settings()
    if not settings.api_keys:  # auth disabled
        return "anonymous"
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    if x_api_key not in settings.api_keys:
        raise HTTPException(status_code=401, detail="invalid API key")
    return x_api_key
```

**Apply `Depends(verify_api_key)` to all MUTATING routes:**
- `POST /api/backtests/run`
- `POST /api/runs/{id}/favorite`
- `POST /api/runs/{id}/cancel`
- `POST /api/universe/refresh`
- `POST /api/reports/generate`

GET routes remain unauth'd in MVP (local dev mostly).

**Settings.api_keys**: `set[str] = Field(default_factory=set)`. Parsed from
comma-separated env `ATLAS20_API_KEYS=key1,key2`.

**Tests:**
- No keys configured → all routes work without header (backward compat)
- Keys configured + valid header → 200
- Keys configured + missing header → 401
- Keys configured + invalid header → 401

### S6 — Rate limit

**Add dep:** `slowapi>=0.1.9`

**File:** `src/atlas20/api/dependencies/ratelimit.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

def _key_func(request):
    # Prefer API key over IP; fall back to remote address
    api_key = request.headers.get("X-API-Key")
    return api_key or get_remote_address(request)

limiter = Limiter(key_func=_key_func)
```

**Wire into `app.py`:**
```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
```

**Apply to routes:**
- `POST /backtests/run`: `@limiter.limit("10/minute")`
- `POST /universe/refresh`: `@limiter.limit("1/minute")`
- `POST /reports/generate`: `@limiter.limit("5/minute")`

**Tests:**
- POST 11 backtests in <60s → 11th returns 429
- POST 2 refresh in <60s → 2nd returns 429
- Distinct API keys have separate limits

### S7 — Path + regex validation (pydantic v2)

**Files:**
- `src/atlas20/api/schemas.py` — add type aliases
- `src/atlas20/api/routes/runs.py`, `reports.py` — use typed Path params

**Pattern:**
```python
from typing import Annotated
from pydantic import StringConstraints

RunId = Annotated[str, StringConstraints(pattern=r"^btk_\d{4,6}$")]
ReportId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,64}$")]

# Routes:
@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: RunId, ...):
    ...
```

FastAPI will return 422 for malformed run_id like `../etc/passwd`.

**Download path validation** (forward-looking for Batch 12 F1):
- Already done in retro batch (`_latest_report_dir` path traversal guard)
- Add similar guard to any future report download route (Batch 12 will reuse)

**Tests:**
- GET `/api/runs/{evil_id}/cancel` where evil_id is `../etc/passwd` → 422
- GET `/api/runs/btk_0142/cancel` → 200 or 409 (existing behavior)

### S8 — Secret hygiene

**Verify:**
- `.env` in `.gitignore` (confirmed)
- No hardcoded API keys / secrets in src/
- `grep -rE "(api[_-]?key|secret|password|token)\s*=\s*['\"][A-Za-z0-9]{16,}" src/` returns empty
- CoinGecko config has `api_key` field from env, not hardcoded

**Tests:**
- `tests/test_no_secrets_in_src.py` — grep test that scans src/ and fails
  if any pattern matches

**Fix any found violations.** Likely none expected.

### S9 — Authorized static delivery

Defer to Batch 12 F1 (actual report download routes). For Batch 11, just
document that `app.py` does NOT mount StaticFiles for `reports/` —
already true. Add a comment near app middleware setup explaining
"all `reports/` access goes through authenticated routes only".

### R7 — Data Sources real (now unblocked)

**File:** `src/atlas20/api/services.py:get_data_sources`

**Decision:** infer last_sync from `data/raw/{provider}/` directory mtime.

```python
def get_data_sources() -> list[DataSource]:
    settings = get_settings()
    raw_root = settings.data_root / "raw"
    return [
        _data_source_status("coingecko", raw_root / "coingecko"),
        _data_source_status("cryptocompare", raw_root / "cryptocompare"),
        # ... existing providers ...
    ]

def _data_source_status(name: str, path: Path) -> DataSource:
    if not path.exists() or not any(path.iterdir()):
        return DataSource(id=name, name=name.title(), status="error", last_sync_seconds=999999)
    latest_mtime = max(f.stat().st_mtime for f in path.rglob("*") if f.is_file())
    age_seconds = int(time.time() - latest_mtime)
    status = "healthy" if age_seconds < 3600 else ("degraded" if age_seconds < 86400 else "error")
    return DataSource(id=name, name=name.title(), status=status, last_sync_seconds=age_seconds)
```

5-minute in-memory cache to avoid scanning on every request:
```python
@lru_cache(maxsize=1)
def _cached_status_with_ttl(): ...  # invalidate via timestamp comparison
```

Or simpler: cache result + timestamp; recompute if older than 300s.

Fall back to mock when `data/raw/` doesn't exist.

**Tests:** synthetic raw dir with manipulated mtimes; assert status mapping.

### R10 — Universe Refresh real

**File:** `src/atlas20/api/services.py:refresh_universe`

**Current:** returns synthesized timestamp.

**Fix decision (Claude):** enqueue a refresh JOB via DB (using same `runs`
table OR a new `jobs` table). For MVP, add a new "refresh" Run with
`strategy="universe_refresh"` and let Batch 12's worker pick it up.

OR: invoke `download_and_cache_raw_data` directly in a worker subprocess
(reuse Batch 9 infra).

**Simpler decision:** enqueue an analog to backtest jobs:
- POST `/universe/refresh` creates a row with `strategy="universe_refresh"`,
  `status="queued"`
- Worker `run_one.py` checks strategy: if `universe_refresh`, calls
  `download_and_cache_raw_data(config)` instead of `run_research_pipeline`
- Add `GET /universe/refresh-status` returning latest refresh row's status

**Tests:**
- POST /refresh → 202 with run_id
- Worker mock processes the job (use ATLAS20_WORKER_MOCK to skip download)
- GET /refresh-status returns the latest job state

### C3 — anchor date UTC clock

Mostly done in retro batch via `_time.today()`. Verify NO other place uses
`date.today()` (which is local time):

```bash
grep -rn "date.today()" src/atlas20/
```

Replace any remaining hits with `from atlas20.api._time import today; today()`.

**Test:** monkeypatch `_time.utc_now` to return a non-UTC datetime; assert
all today() calls reflect the override.

## Files expected

- `pyproject.toml` — add `slowapi>=0.1.9`
- `src/atlas20/api/settings.py` — env validator for CORS in prod + docs
- `src/atlas20/api/app.py` — apply auth + rate limit + docs gate
- `src/atlas20/api/dependencies/__init__.py`, `auth.py`, `ratelimit.py` (NEW)
- `src/atlas20/api/schemas.py` — add `RunId`, `ReportId` typed aliases
- `src/atlas20/api/routes/{runs,backtests,reports,universe}.py` — apply
  Depends + rate limits + typed path params
- `src/atlas20/api/services.py` — R7/R10 real implementations
- `src/atlas20/api/worker/run_one.py` — handle universe_refresh job kind
- `tests/test_auth.py` (NEW)
- `tests/test_rate_limit.py` (NEW)
- `tests/test_path_validation.py` (NEW)
- `tests/test_no_secrets_in_src.py` (NEW)
- `tests/test_data_sources_real.py` (NEW)
- `tests/test_universe_refresh_real.py` (NEW)

## Out of scope

- S5 JWT/OAuth (deferred — local MVP doesn't need)
- Auth on GET routes (deferred to later batch if needed)
- Actual report generation (Batch 12)
- Distributed rate limiting (single-instance for MVP)
- HTTPS termination (deployment concern — Batch 14)

## Acceptance

- `python -m pytest tests/ -q` → 220 + ~30 = ~250 passed
- `cd apps/web && npm run test -- --run` → still 132 (frontend unchanged
  unless API key prompt added; if so +1)
- Lint + typecheck clean
- Manual:
  - Start server with `ATLAS20_ENV=prod` + no CORS → boot fails
  - Start with `ATLAS20_API_KEYS=key1`; POST /backtests without header → 401
  - POST /backtests with `X-API-Key: key1` 11 times → 429 on 11th
  - POST /runs/`../evil`/cancel → 422 (regex)
  - POST /universe/refresh → 202; worker processes it; raw/ has new file mtime
  - GET /data/sources reflects real raw/ mtime → status healthy

## Determinism

All time via `_time.utc_now()`. Rate limit storage: in-memory (per process,
acceptable for MVP). API keys are env-driven.
