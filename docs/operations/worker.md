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

Worker startup performs PID-scoped recovery: it only marks running jobs failed when they were claimed by the current worker PID before restart. This avoids failing sibling workers' active runs.

The FastAPI application lifespan still performs broad stale-heartbeat recovery as the central coordinator. It marks running jobs failed when their heartbeat is missing or stale after the configured startup check.
