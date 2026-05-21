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

`prometheus_client` counters live in **per-process memory**. The API and worker run in separate processes (see `docker-compose.yml` `backend` + `worker` services), so a single scrape against the API's `/metrics` would miss every counter the worker increments — `atlas20_backtests_total`, `atlas20_report_generations_total`, and `atlas20_backtest_duration_seconds` would all appear stuck at zero for any work the worker performed.

The worker therefore exposes its own `/metrics` endpoint on a dedicated port (default `8001`, overridable via `ATLAS20_WORKER_METRICS_PORT`). Prometheus must be configured with **both** scrape targets:

```yaml
scrape_configs:
  - job_name: atlas20-api
    static_configs:
      - targets: ["atlas20-backend:8000"]
  - job_name: atlas20-worker
    static_configs:
      - targets: ["atlas20-worker:8001"]
```

Queries that combine API-side and worker-side counts must aggregate across the `instance` (and `job`) labels, e.g.

```promql
sum without (instance, job) (atlas20_backtests_total)
```

Dashboards and alerts authored before this split (i.e. before commit b4b9ed8) need this aggregation added; otherwise they read only one process's view and may falsely report zero traffic.

## Metrics correctness caveats

**Counters may slightly over-count on rollback.** Backtest terminal counters and report-generation counters are incremented before the surrounding DB transaction commits. A commit failure leaves Prometheus over-reporting by 1. We accept this as Prometheus counters are monotonic and commit failures are rare in this codebase. Track via the existing 5xx alert if the divergence ever becomes visible.

## Scheduler Lock

The weekly digest scheduler uses `{ATLAS20_DATA_ROOT}/.scheduler.lock` for single-node multi-worker leader election. This prevents duplicate scheduled jobs across multiple uvicorn or gunicorn workers on one host. Multi-node deployments need a Redis or database-backed leader election mechanism before enabling the scheduler on more than one host.
