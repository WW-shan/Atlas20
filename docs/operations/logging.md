# Atlas20 Logging and Observability Operations

## Log Rotation

When `ATLAS20_LOG_FILE_PATH` is set, the API writes the same structured JSON log stream to that file and to stdout. The file handler rotates at 50 MB with 10 retained backups, capping local log storage at roughly 500 MB per API process.

For the MVP, run either local file rotation through this setting or rely on container, journald, or platform log rotation. Development retention is 30 days; production retention should be set by the deployment log pipeline.

## Secret Redaction

Structured log events are redacted before JSON rendering. Header fields named `X-API-Key`, `Authorization`, or `Cookie` are replaced with `***REDACTED***` case-insensitively, including nested `headers` dictionaries. Fields named `secret_key`, `secret`, or `api_key` are also redacted, and string values matching `sk_[a-zA-Z0-9]{20,}` are masked in place.

## Metrics Access

The MVP `/metrics` endpoint is unauthenticated, matching the current GET-route exposure policy. Production deployments should keep the API bound to a private interface or place `/metrics` behind a reverse proxy allow-list such as nginx internal IP rules.

`/readyz` is excluded from Prometheus instrumentation because the probe is too short-lived (< 5ms typical) for histogram bucket distribution to be meaningful. Alert on 503 rate via the access log instead (`status_code >= 500 AND path == "/readyz"`).

## Metrics correctness caveats

**Counters may slightly over-count on rollback.** Backtest terminal counters and report-generation counters are incremented before the surrounding DB transaction commits. A commit failure leaves Prometheus over-reporting by 1. We accept this as Prometheus counters are monotonic and commit failures are rare in this codebase. Track via the existing 5xx alert if the divergence ever becomes visible.

## Scheduler Lock

The weekly digest scheduler uses `{ATLAS20_DATA_ROOT}/.scheduler.lock` for single-node multi-worker leader election. This prevents duplicate scheduled jobs across multiple uvicorn or gunicorn workers on one host. Multi-node deployments need a Redis or database-backed leader election mechanism before enabling the scheduler on more than one host.
