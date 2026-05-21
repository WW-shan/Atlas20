# Atlas20 Worker Operations

## Launching Workers

Run a single worker with:

```bash
PYTHONPATH=src python -m atlas20.api.worker
```

Run multiple local workers with the spawn helper:

```bash
PYTHONPATH=src ATLAS20_WORKERS=2 python -m atlas20.api.worker.spawn
```

`ATLAS20_WORKERS` controls how many child worker processes the spawn helper starts. Each child sets `ATLAS20_WORKERS=1` for itself to avoid recursive fan-out.

`PYTHONPATH=src` is only needed when running from a source checkout. Packaged installs can omit it and still use `python -m atlas20.api.worker` so the worker bootstrap configures `PROMETHEUS_MULTIPROC_DIR` before worker modules import.

## Runtime Settings

Workers use the same `ATLAS20_DB_URL`, `ATLAS20_REPORT_ROOT`, `ATLAS20_PROJECT_ROOT`, and `ATLAS20_RUN_TIMEOUT_SECONDS` settings as the API process.

`ATLAS20_WORKER_MOCK=1` runs the subprocess entry point in mock mode for tests and local smoke checks. Mock mode writes deterministic artifacts without running the research pipeline.

`ATLAS20_WORKER_HEARTBEAT_INTERVAL_SECONDS` defaults to `2.0`. `ATLAS20_WORKER_CANCEL_GRACE_SECONDS` defaults to `3.0`. Together they set the expected worst-case cancel latency to about 5 seconds before a cancelled subprocess is terminated or killed.

## Packaged Installs

Workers launch through Python module entry points and the standard library `subprocess` module. A packaged install needs no separate worker binary or extra runtime step beyond installing Atlas20 and running the module commands above.

## Restart Recovery

Worker startup runs a narrow PID-scoped sweep (`recover_runs_owned_by_pid`) that fails any running rows whose recorded `worker_pid` happens to equal the new worker process's PID. Under normal restart this is a no-op because the new PID rarely matches a previously-recorded one; the sweep exists as a defensive guard against accidental PID reuse and never touches sibling workers' active runs.

The FastAPI application lifespan performs the actual restart recovery as the central coordinator. `recover_stale_runs` marks running jobs failed when their `heartbeat_at` is missing or older than the configured staleness threshold; it does not consult `worker_pid` at all.

## Healthcheck

The worker's docker-compose healthcheck probes both the HTTP listener thread (port `8001`) and the queue loop. The Python one-liner scrapes `/metrics`, extracts `atlas20_worker_last_poll_timestamp_seconds`, and fails the check if the gauge is older than 30 seconds or absent entirely. A stuck queue loop with a healthy listener thread is therefore caught, whereas a bare `curl /metrics` 200 would have passed.

Two code paths refresh the gauge:

1. The worker's main queue loop calls `record_worker_poll_tick()` at the top of every iteration, so an idle worker still publishes a fresh timestamp at the configured `ATLAS20_WORKER_POLL_INTERVAL_SECONDS` cadence (default `2.0s`).
2. The per-run heartbeat thread calls `record_worker_poll_tick()` every `ATLAS20_WORKER_HEARTBEAT_INTERVAL_SECONDS` (default `2.0s`) for the duration of an in-flight backtest. Without this path the gauge would age past the 30s threshold during any run longer than that, and docker would kill a perfectly healthy worker.

The 30-second freshness window assumes both interval settings stay well below it. If you raise either `ATLAS20_WORKER_POLL_INTERVAL_SECONDS` or `ATLAS20_WORKER_HEARTBEAT_INTERVAL_SECONDS`, widen the healthcheck window in `docker-compose.yml` to keep at least one stamp inside every check interval.
