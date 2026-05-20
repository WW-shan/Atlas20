# Batch 14 — Phase O: Observability

## Goal

Implement Phase O remaining items from `docs/redesign/ROADMAP.md`: Prometheus
metrics + business gauges/counters, Sentry SDK env-gated, `/healthz` + `/readyz`
endpoints, log rotation + secret redaction. Also close the deferred Batch 13
finding R1-Opus-I6 (multi-worker scheduler dedup via file-lock).

Phase O completion unblocks ops/SRE for production-readiness (MS-3) — see
ROADMAP MS-3 checklist.

## Existing infrastructure (DO NOT duplicate)

| Item | Status | File |
|---|---|---|
| O1 structlog JSON formatter | ✅ done | `src/atlas20/api/logging_config.py` |
| O2 X-Request-ID middleware | ✅ done | `src/atlas20/api/middleware/request_id.py` |
| Access log | ✅ done | `src/atlas20/api/middleware/access_log.py` (excludes /healthz, /metrics) |

This batch ADDS what's missing; do not refactor what already works.

## Scope (~450 LOC + ~16 tests)

### O3 — Prometheus instrumentation + /metrics

**Files:** new `src/atlas20/api/middleware/metrics.py`, `src/atlas20/api/routes/health.py`, mods to `src/atlas20/api/app.py`.

Add `prometheus-fastapi-instrumentator` to deps. Wire it in app lifespan:

```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/healthz", "/readyz"],  # /metrics auto-excluded
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
```

Business metrics (Counter + Histogram, registered at module top):

- `atlas20_backtests_total{status}` Counter — incremented in `services.list_runs`/`runs_repo.update_status` on terminal transition (status ∈ completed|failed|cancelled). Existing transitions are in the worker; wire there.
- `atlas20_backtest_duration_seconds` Histogram — observe `(finished_at - started_at).total_seconds()` on terminal status. Same hook point.
- `atlas20_report_generations_total{format,status}` Counter — wrap `generate_run_report_with_warnings` (services_report.py).
- `atlas20_rate_limit_hits_total{route}` Counter — wired in the SlowAPI 429 handler (dependencies/ratelimit.py).

**Auth on /metrics:** in MVP `/metrics` is unauthenticated (per `docs/operations/security.md` GET-routes MVP gate). Document this; production behind reverse proxy (nginx allow internal IPs).

**Test:** new `tests/test_metrics.py`:
- GET /metrics → 200 + `text/plain` content + contains `atlas20_backtests_total` family
- After registering a completed run, the counter increments
- /metrics is excluded from access log (verify via caplog)

### O4 — Sentry SDK env-gated

**Files:** `src/atlas20/api/settings.py` (add `sentry_dsn: str | None = None`), `src/atlas20/api/app.py` (init in lifespan).

```python
if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        traces_sample_rate=0.0,  # MVP: errors only, no perf monitoring
        send_default_pii=False,
        before_send=_scrub_sensitive_headers,  # see O6
        integrations=[FastApiIntegration()],
    )
```

Add `sentry-sdk[fastapi]` to deps.

**Test:** new `tests/test_sentry.py`:
- `settings.sentry_dsn=None` → `sentry_sdk.init` NOT called
- `settings.sentry_dsn="https://fake@example.com/1"` + monkeypatch `sentry_sdk.init` → called with expected kwargs
- `before_send` callback strips `X-API-Key` from event request headers

### O5 — /healthz + /readyz

**File:** new `src/atlas20/api/routes/health.py`.

`/healthz` → static 200 `{status: "ok"}`. No DB query. Fast (< 1ms).

`/readyz` → checks:
- DB connection (`SELECT 1` via `get_session`)
- `report_root` writable (`os.access(settings.report_root, os.W_OK)`)
- Returns 200 `{status: "ready", checks: {db: "ok", reports: "ok"}}` on success, 503 with the failing check on failure.

Both unauth, both excluded from access log AND /metrics scrape.

**Test:** new `tests/test_health.py`:
- GET /healthz → 200 + body shape
- GET /readyz happy path → 200 + checks dict
- DB down (close session) → 503 + `checks.db == "fail"`
- report_root non-writable (chmod 444; skip on Windows) → 503 + `checks.reports == "fail"`

### O6 — Log rotation + secret redaction

**Files:** `src/atlas20/api/logging_config.py`, `src/atlas20/api/middleware/access_log.py`, new `src/atlas20/api/_log_redact.py`.

**Redaction:**

A structlog processor (added to `shared_processors` in `logging_config.py`)
walks the event dict and replaces:
- `X-API-Key`, `Authorization`, `Cookie` → `"***REDACTED***"` (case-insensitive
  match against keys; covers nested `headers` dicts)
- Any string value matching `r"sk_[a-zA-Z0-9]{20,}"` (Sentry/Stripe-style) →
  `"***REDACTED***"`
- Existing `secret_key` field name → `"***REDACTED***"`

```python
SENSITIVE_KEYS = {"x-api-key", "authorization", "cookie", "secret_key", "secret", "api_key"}
SECRET_VALUE_PATTERN = re.compile(r"sk_[a-zA-Z0-9]{20,}")

def redact_sensitive(_logger, _name, event_dict: dict) -> dict:
    def walk(value):
        if isinstance(value, dict):
            return {k: ("***REDACTED***" if k.lower() in SENSITIVE_KEYS else walk(v)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(walk(v) for v in value)
        if isinstance(value, str) and SECRET_VALUE_PATTERN.search(value):
            return SECRET_VALUE_PATTERN.sub("***REDACTED***", value)
        return value
    return walk(event_dict)
```

Wire into both `shared_processors` (BEFORE JSONRenderer) AND access_log's
log-call (since access_log emits via `structlog.get_logger("atlas20.api.access")`,
the processor chain catches it automatically — verify).

**Rotation:**

Add `logging.handlers.RotatingFileHandler` when `settings.log_file_path` is
set (default `None` → stdout only):
- maxBytes 50 MB, backupCount 10
- Same JSON formatter as stdout handler

Document in `docs/operations/security.md` (or new `docs/operations/logging.md`):
- MVP: rotate locally OR rely on container/journald
- Retention: 30 days for dev, configurable in prod
- All sensitive fields auto-redacted per O6

**Test:** new `tests/test_log_redact.py`:
- structlog event with `headers={"X-API-Key": "real-key"}` → emitted dict has `X-API-Key: "***REDACTED***"`
- Nested case: `request={"headers": {"Authorization": "Bearer abc"}}` → nested key also redacted
- Stripe-style secret in message body → masked
- Case-insensitive key matching (`x-api-key` and `X-API-Key` both hit)
- Mixed allowed + redacted keys preserved correctly

new `tests/test_log_rotation.py`:
- Configure RotatingFileHandler with maxBytes=1KB → write 2KB worth → assert rollover file created
- Skip on Windows if pytest can't write/read the rotation files reliably

### B13-deferred R1-Opus-I6 — Multi-worker scheduler dedup

**Files:** `src/atlas20/api/scheduler.py`.

**Problem:** Each uvicorn worker boots its own `AsyncIOScheduler` → digest
generates N× per Monday in `gunicorn -w 4`.

**Decision (Claude):** File-lock based leader election. The first worker to
acquire `{settings.data_root}/.scheduler.lock` (via `fcntl.flock` on POSIX or
`msvcrt.locking` on Windows; library `filelock` handles both) becomes the
scheduler owner; others skip startup. Release on shutdown.

```python
# scheduler.py
from filelock import FileLock, Timeout

def start_scheduler(...) -> AsyncIOScheduler | None:
    if os.environ.get("ATLAS20_DISABLE_SCHEDULER") == "1":
        return None
    lock_path = settings.data_root / ".scheduler.lock"
    lock = FileLock(str(lock_path), timeout=0)
    try:
        lock.acquire()  # non-blocking
    except Timeout:
        logger.info("scheduler lock held by another worker; skipping")
        return None
    # Continue with AsyncIOScheduler setup as before; stash `lock` for shutdown
    ...
```

Already have `filelock` dep from Batch 7 (sqlite migration lock) — verify, add
if missing.

**Test:** new `tests/test_scheduler_lock.py`:
- First call acquires lock → returns scheduler
- Second call (lock held by separate process — use multiprocessing) → returns None
- Shutdown releases lock; next start succeeds
- `ATLAS20_DISABLE_SCHEDULER=1` always returns None regardless of lock

### Algorithm decisions

- **/metrics unauth** in MVP (per security.md). Production gates behind nginx
  allow-list.
- **Sentry traces_sample_rate=0.0** — errors only, no APM in MVP.
- **`/readyz` checks DB + report_root** — narrow to what callers actually
  depend on. Don't probe external APIs (CoinGecko etc) since those have rate
  limits.
- **Rotation maxBytes 50 MB / backupCount 10** — 500 MB ceiling per pod.
  Production should ship logs to central aggregator; rotation is the local
  safety net.
- **File-lock scheduler election** — simpler than Redis/Postgres advisory lock;
  works for single-node multi-worker deployments. For multi-node, document the
  upgrade path (Redis-backed leader-elect).

## Tests (~16 new)

1. `tests/test_metrics.py` — 4 tests (endpoint exposure, counter increments, exclusion from access log, /metrics shape)
2. `tests/test_sentry.py` — 3 tests (disabled when DSN=None, init args, before_send redaction)
3. `tests/test_health.py` — 4 tests (/healthz ok, /readyz happy + DB-down + reports-down)
4. `tests/test_log_redact.py` — 3 tests (header redaction, nested, value pattern)
5. `tests/test_log_rotation.py` — 1 test (rollover triggers; Windows-skippable)
6. `tests/test_scheduler_lock.py` — 4 tests (acquire, contention, release, ENV gate)

Frontend unchanged at 132.

## Out of scope

- Distributed tracing (OpenTelemetry / Tempo) — track for post-MS-3.
- Custom Grafana dashboards — out of code scope; ops team responsibility.
- Multi-node scheduler election (Redis advisory lock) — single-node MVP only.
- Log forwarding to ELK / Loki — ops infra concern.

## Acceptance

- `python -m pytest tests/ -x -q` → 295 → ~311 (+16)
- `cd apps/web && npm run test -- --run` → 132 unchanged
- `cd apps/web && npm run lint && npm run typecheck` → clean
- Manual: `curl http://localhost:8000/metrics` → 200 with Prometheus exposition
- Manual: `curl http://localhost:8000/healthz` → 200 fast
- Manual: `curl http://localhost:8000/readyz` → 200 with checks dict
- Manual: start two workers (`uvicorn ... --workers 2 --no-access-log`) and
  confirm only ONE schedules the weekly digest job (log line "scheduler lock
  held by another worker; skipping" from the second)
- Manual: trigger a log event containing `X-API-Key: abc123` → stdout shows
  `***REDACTED***`

## Files expected to change

| File | Action | Est LOC |
|---|---|---|
| `src/atlas20/api/middleware/metrics.py` | New | +30 (mostly instrumentator wiring) |
| `src/atlas20/api/_metrics.py` | New: Counter/Histogram registry | +50 |
| `src/atlas20/api/routes/health.py` | New: /healthz + /readyz | +60 |
| `src/atlas20/api/_log_redact.py` | New: structlog redact processor | +50 |
| `src/atlas20/api/logging_config.py` | Add redact processor + RotatingFileHandler | +30 |
| `src/atlas20/api/scheduler.py` | filelock leader election | +25 |
| `src/atlas20/api/settings.py` | Add `sentry_dsn`, `log_file_path` | +10 |
| `src/atlas20/api/app.py` | Lifespan: Sentry init + metrics + health routes | +30 |
| `src/atlas20/api/services_report.py` | Wire `atlas20_report_generations_total` | +10 |
| `src/atlas20/api/dependencies/ratelimit.py` | Wire `atlas20_rate_limit_hits_total` | +10 |
| `src/atlas20/api/repositories/runs_repo.py` | Wire `atlas20_backtests_total` + duration | +15 |
| `pyproject.toml` + requirements | Add `prometheus-fastapi-instrumentator`, `sentry-sdk[fastapi]`, verify `filelock` | +5 |
| `docs/operations/logging.md` | New: rotation + redaction policy | +60 |
| `tests/test_metrics.py` | New | +50 |
| `tests/test_sentry.py` | New | +40 |
| `tests/test_health.py` | New | +50 |
| `tests/test_log_redact.py` | New | +40 |
| `tests/test_log_rotation.py` | New | +25 |
| `tests/test_scheduler_lock.py` | New | +60 |
| **Total** | | **~650 (380 source + 270 tests + docs)** |
