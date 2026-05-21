# Atlas20 Logging and Observability Operations

## Log Rotation

When `ATLAS20_LOG_FILE_PATH` is set, the API writes the same structured log stream to that file and to stdout. The format defaults to JSON; setting `ATLAS20_LOG_FORMAT=text` switches both stdout and the file to a plain-text `asctime level [logger] message` layout (see `src/atlas20/api/logging_config.py`). The file handler rotates at 50 MB with 10 retained backups, capping local log storage at roughly 500 MB per API process.

For the MVP, run either local file rotation through this setting or rely on container, journald, or platform log rotation. Development retention is 30 days; production retention should be set by the deployment log pipeline.

## Secret Redaction

Structured log events are redacted before JSON rendering. Header fields named `X-API-Key`, `Authorization`, or `Cookie` are replaced with `***REDACTED***` case-insensitively, including nested `headers` dictionaries. Fields named `secret_key`, `secret`, or `api_key` are also redacted, and string values matching `sk_[a-zA-Z0-9]{20,}` are masked in place.

## Metrics Access

The MVP `/metrics` endpoint is unauthenticated, matching the current GET-route exposure policy. Production deployments should keep the API bound to a private interface or place `/metrics` behind a reverse proxy allow-list such as nginx internal IP rules.

`/readyz` is excluded from Prometheus instrumentation because the probe is too short-lived (< 5ms typical) for histogram bucket distribution to be meaningful. Alert on 503 rate via the access log instead (`status >= 500 AND path == "/readyz"`; the access-log JSON field is `status`, not `status_code` — see `src/atlas20/api/middleware/access_log.py`).

## Prometheus dual scrape targets (API + worker)

`prometheus_client` counters live in **per-process memory**, with each process maintaining its own local registry. The API and worker processes emit largely disjoint series, but a few — `atlas20_backtests_total` and `atlas20_backtest_duration_seconds` — are emitted by both: the worker increments them on the main run path (and on its own startup recovery), and the API increments them during lifespan startup recovery. Scrape both endpoints to collect every contribution.

| Metric | Process | Notes |
| --- | --- | --- |
| `http_requests_total{method,handler,status}` | API | HTTP instrumentation via `prometheus-fastapi-instrumentator`. Default metric name (no namespace configured); `status` is grouped (`should_group_status_codes=True`) so the label is `"2xx" / "3xx" / "4xx" / "5xx"`, not the raw code. |
| `atlas20_rate_limit_hits_total{route}` | API | slowapi handler |
| `atlas20_report_generations_total{format,status}` | API | `completed`/`failed` incremented inside `services_report.generate_run_report_with_warnings` (invoked from POST `/api/reports/generate` and the weekly digest scheduler); `skipped` incremented in the POST `/api/reports/generate` handler itself. |
| `atlas20_backtests_total{status}` | Worker (main path) + API (lifespan recovery only) | Incremented per terminal transition. The API process emits this only during lifespan startup when `recover_stale_runs` reclassifies orphaned runs as failed; the dominant emitter is the worker subprocess via multiproc aggregation. |
| `atlas20_backtest_duration_seconds` | Worker (main path) + API (lifespan recovery only) | Histogram; multiproc-aggregated. The API contribution comes from `recover_stale_runs` observing a duration when reclassifying orphaned runs as failed during lifespan startup; the dominant emitter is the worker subprocess. |

Configure Prometheus with both scrape targets:

```yaml
scrape_configs:
  - job_name: atlas20-api
    static_configs:
      - targets: ["backend:8000"]
  - job_name: atlas20-worker
    static_configs:
      - targets: ["worker:8001"]
```

The hostnames `backend` and `worker` are the dev `docker-compose.yml` service names that resolve inside the compose project network; production deployments must substitute the actual DNS-resolvable hostnames their orchestrator assigns.

Queries that span both processes — `atlas20_backtests_total` and the histogram `atlas20_backtest_duration_seconds` are both emitted by the worker (main path) and by the API (lifespan recovery only), so spanning queries should aggregate across the `instance` and `job` labels:

```promql
sum without (instance, job) (atlas20_backtests_total)
```

INFO: The API contribution to both series is bounded and small because it only comes from lifespan startup recovery. No PromQL adjustment is needed beyond the `sum without (instance, job)` example above.

Histogram queries - use `_sum` / `_count` / `_bucket` series, not the base name:

```promql
# p95 backtest duration over 1h, across all worker and API processes
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

### Windows port-bind semantics (multi-worker)

`python -m atlas20.api.worker.spawn` with `ATLAS20_WORKERS>1` runs multiple worker processes on one host. On Linux every worker after the first raises `EADDRINUSE` when binding port 8001 and `start_metrics_server` (`src/atlas20/api/worker/main.py`) catches the error and proceeds without its own HTTP listener. On Windows, `http.server.HTTPServer.allow_reuse_address = 1` plus the OS-level `SO_REUSEADDR` semantics let every child socket bind to 8001 without raising; Windows then routes incoming connections to only one of the bound sockets (typically the first), so additional workers' `start_metrics_server` log lines (`"listening on port 8001 (multiproc=True)"`) are emitted but never reachable from Prometheus. Metric values are still correct because every worker writes counters to the shared `PROMETHEUS_MULTIPROC_DIR` mmap files that the reachable worker's `MultiProcessCollector` aggregates.

If your monitoring requires every worker's HTTP endpoint to actually receive scrapes (e.g. for per-instance liveness alerts in a Prometheus job), launch each worker independently — not via `spawn.spawn_workers`, which currently shares parent env across all children — and give each one a distinct `ATLAS20_WORKER_METRICS_PORT`. **Set `ATLAS20_WORKER_MULTIPROC_SKIP_WIPE=1` on every worker after the first**; otherwise each newly launched worker's `__main__.py` bootstrap will wipe `PROMETHEUS_MULTIPROC_DIR` and erase the prior workers' mmap files. The first worker should leave `ATLAS20_WORKER_MULTIPROC_SKIP_WIPE` unset so it performs the canonical startup wipe of stale dead-pid files. Because all workers continue to share `PROMETHEUS_MULTIPROC_DIR`, every endpoint will serve the same aggregated counter snapshot; the only thing that changes is that every endpoint is independently reachable. True per-process metric isolation would require also giving each worker a distinct `PROMETHEUS_MULTIPROC_DIR`, which sacrifices cross-process counter aggregation and is rarely worth it.

## Metrics correctness caveats

**Counters may slightly over-count on rollback.** Backtest terminal counters and report-generation counters are incremented before the surrounding DB transaction commits. A commit failure leaves Prometheus over-reporting by 1. We accept this as Prometheus counters are monotonic and commit failures are rare in this codebase. Track via the existing 5xx alert if the divergence ever becomes visible.

## Scheduler Lock

The weekly digest scheduler uses `{ATLAS20_DATA_ROOT}/.scheduler.lock` for single-node multi-worker leader election. This prevents duplicate scheduled jobs across multiple uvicorn or gunicorn workers on one host. Multi-node deployments need a Redis or database-backed leader election mechanism before enabling the scheduler on more than one host.
