# Atlas20 Logging and Observability Operations

## Log Rotation

When `ATLAS20_LOG_FILE_PATH` is set, the API writes the same structured JSON log stream to that file and to stdout. The file handler rotates at 50 MB with 10 retained backups, capping local log storage at roughly 500 MB per API process.

For the MVP, run either local file rotation through this setting or rely on container, journald, or platform log rotation. Development retention is 30 days; production retention should be set by the deployment log pipeline.

## Secret Redaction

Structured log events are redacted before JSON rendering. Header fields named `X-API-Key`, `Authorization`, or `Cookie` are replaced with `***REDACTED***` case-insensitively, including nested `headers` dictionaries. Fields named `secret_key`, `secret`, or `api_key` are also redacted, and string values matching `sk_[a-zA-Z0-9]{20,}` are masked in place.

## Metrics Access

The MVP `/metrics` endpoint is unauthenticated, matching the current GET-route exposure policy. Production deployments should keep the API bound to a private interface or place `/metrics` behind a reverse proxy allow-list such as nginx internal IP rules.

`/readyz` is excluded from Prometheus instrumentation because the probe is too short-lived (< 5ms typical) for histogram bucket distribution to be meaningful. Alert on 503 rate via the access log instead (`status_code >= 500 AND path == "/readyz"`).

## Prometheus dual scrape targets (API + worker)

`prometheus_client` counters live in **per-process memory**. The API process and worker process emit different metrics; each must be scraped on its own endpoint.

| Metric | Process | Notes |
| --- | --- | --- |
| `atlas20_request_total{status,...}` | API | HTTP instrumentation via fastapi-instrumentator |
| `atlas20_rate_limit_hits_total{route}` | API | slowapi handler |
| `atlas20_report_generations_total{format,status}` | API | Incremented inside POST `/api/reports/generate` handler |
| `atlas20_backtests_total{status}` | Worker | Incremented in run_one subprocess; multiproc-aggregated |
| `atlas20_backtest_duration_seconds` | Worker | Histogram; multiproc-aggregated |

Configure Prometheus with both scrape targets:

```yaml
scrape_configs:
  - job_name: atlas20-api
    static_configs:
      - targets: ["atlas20-backend:8000"]
  - job_name: atlas20-worker
    static_configs:
      - targets: ["atlas20-worker:8001"]
```

Counter queries that span both processes (none currently, but if you add one):

```promql
sum without (instance, job) (atlas20_backtests_total)
```

Histogram queries - use `_sum` / `_count` / `_bucket` series, not the base name:

```promql
# p95 backtest duration over 1h, across all worker processes
histogram_quantile(
  0.95,
  sum by (le) (
    rate(atlas20_backtest_duration_seconds_bucket[1h])
  )
)
```

Worker counters are aggregated across the run_one subprocess via `PROMETHEUS_MULTIPROC_DIR` (see `src/atlas20/api/worker/__main__.py`). The bootstrap is essential - without it every backtest completion is silently dropped.

### Multiprocess metric file lifecycle

The worker's `PROMETHEUS_MULTIPROC_DIR` (default
`{ATLAS20_DATA_ROOT}/.prom-multiproc-worker`) accumulates per-pid mmap
files for every `run_one` subprocess. The bootstrap shim
(`src/atlas20/api/worker/__main__.py`) wipes the directory on every
worker startup to prevent unbounded growth, per upstream
`prometheus_client` guidance.

For the multi-worker local helper (`atlas20.api.worker.spawn`), the
parent process wipes the directory once and sets
`ATLAS20_WORKER_MULTIPROC_SKIP_WIPE=1` on each spawned child so the
children do not race-wipe each other's mmap files.

On Windows, a wipe that races with an in-flight subprocess's open mmap
will fail to delete the locked file; this is acceptable -- the wipe is
`ignore_errors=True` and the leftover is bounded by the number of
in-flight subprocesses at restart time (typically 1).

## Metrics correctness caveats

**Counters may slightly over-count on rollback.** Backtest terminal counters and report-generation counters are incremented before the surrounding DB transaction commits. A commit failure leaves Prometheus over-reporting by 1. We accept this as Prometheus counters are monotonic and commit failures are rare in this codebase. Track via the existing 5xx alert if the divergence ever becomes visible.

## Scheduler Lock

The weekly digest scheduler uses `{ATLAS20_DATA_ROOT}/.scheduler.lock` for single-node multi-worker leader election. This prevents duplicate scheduled jobs across multiple uvicorn or gunicorn workers on one host. Multi-node deployments need a Redis or database-backed leader election mechanism before enabling the scheduler on more than one host.
