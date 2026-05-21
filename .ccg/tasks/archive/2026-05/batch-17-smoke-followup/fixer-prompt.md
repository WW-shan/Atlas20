ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
You are the **codex fixer** for Atlas20 Batch 17 round-2 follow-up. Two
reviewers (Opus 4.7 in main context + fresh codex reviewer at session
019e4874-df38-7d13-81a1-3de13eeab10e) ran round-2 review on commits
`3bfb2df..HEAD` and surfaced 7 findings. Claude has made architectural
decisions for every one of them — codex executes; codex does not relitigate
the design.

**Background:** B17 #2 (`89a8b71 fix(api): worker exposes /metrics on
dedicated port`) is the headline regression. It started a Prometheus
HTTP server in the worker PARENT process, but every backtest completion
counter (`atlas20_backtests_total{status="completed"}`,
`atlas20_backtest_duration_seconds`) is incremented inside a
`python -m atlas20.api.worker.run_one` SUBPROCESS. The subprocess has
its own per-process registry; counters die with the subprocess and
parent /metrics never sees them. Codex smoke independently reproduced
this — completed runs leave the API /metrics counter at 0.0.

**Each finding = one independent commit.** Run pytest + verify_release
after each. Commit messages use `fix(api|infra|docs|test): batch 17 r2 — <one-line summary>`.

Branch: `redesign/r3-premium`. Start from current HEAD `4f7c9f0`.

---

## C1 — Worker metrics must aggregate across run_one subprocess (the real C-resolved)

**Files:**
- new `src/atlas20/api/worker/__main__.py`
- `src/atlas20/api/worker/main.py`
- `src/atlas20/api/worker/run_one.py`
- `src/atlas20/api/settings.py`
- `docker-compose.yml`
- `README.md`
- new `tests/test_worker_metrics_multiproc.py`

**Problem:** `_metrics.py` uses default `Counter`/`Histogram` which
write to per-process in-memory storage. `run_one.py` is a subprocess
launched via `subprocess.Popen([sys.executable, "-m",
"atlas20.api.worker.run_one", run_id])`. Counters incremented at
`run_one.py:212-220` (`RunsRepo.update_metrics_from_completion` →
`_record_terminal_transition` → `record_backtest_terminal`) live in
the child registry and are lost on child exit. Parent's
`start_http_server` only exposes parent's registry.

**Decision (Claude):** Use prometheus_client's official multiprocess
mode via `PROMETHEUS_MULTIPROC_DIR`. Setup:

1. **New entry shim** `src/atlas20/api/worker/__main__.py` — sets
   `PROMETHEUS_MULTIPROC_DIR` **before any atlas20 import** (must be
   set before `from prometheus_client import Counter` runs):

   ```python
   """Bootstrap entry: sets PROMETHEUS_MULTIPROC_DIR before importing
   atlas20 modules, so per-process Counter writes land in shared mmap
   files that the parent /metrics aggregates. Required because run_one
   runs in a subprocess; without this, its counter increments vanish on
   subprocess exit.
   """
   from __future__ import annotations

   import os
   from pathlib import Path

   _data_root = Path(os.environ.get("ATLAS20_DATA_ROOT", "data"))
   _multiproc_dir = _data_root / ".prom-multiproc-worker"
   _multiproc_dir.mkdir(parents=True, exist_ok=True)
   os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(_multiproc_dir))

   from atlas20.api.worker.main import main  # noqa: E402

   if __name__ == "__main__":
       main()
   ```

2. **`worker/main.py` `start_metrics_server`** — when
   `PROMETHEUS_MULTIPROC_DIR` is set, build a fresh `CollectorRegistry`
   with `MultiProcessCollector` attached and bind the HTTP server
   against it. Otherwise fall back to default single-process behavior
   (so unit tests that don't bootstrap still work):

   ```python
   def start_metrics_server(port: int) -> None:
       global _metrics_server_started
       with _metrics_server_lock:
           if _metrics_server_started:
               return
           multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
           if multiproc_dir:
               from prometheus_client import CollectorRegistry, multiprocess
               registry = CollectorRegistry()
               multiprocess.MultiProcessCollector(registry)
               start_http_server(port, registry=registry)
           else:
               start_http_server(port)
           _metrics_server_started = True
           logger.info("worker prometheus /metrics listening on port %d (multiproc=%s)",
                       port, bool(multiproc_dir))
   ```

3. **subprocess.Popen** in `worker/main.py:160-164` — pass `env=` so the
   child inherits `PROMETHEUS_MULTIPROC_DIR`:

   ```python
   proc = subprocess.Popen(
       [sys.executable, "-m", "atlas20.api.worker.run_one", run_id],
       stdout=subprocess.PIPE,
       stderr=subprocess.PIPE,
       env=os.environ.copy(),
   )
   ```

4. **`run_one.py`** — add an atexit handler that calls
   `prometheus_client.multiprocess.mark_process_dead(os.getpid())` so
   the shared dir doesn't accumulate dead-PID files for histograms.
   Guard with `if PROMETHEUS_MULTIPROC_DIR in env`:

   ```python
   # At top of run_one.py module (after imports):
   import atexit

   def _cleanup_metrics_files() -> None:
       if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
           from prometheus_client import multiprocess
           multiprocess.mark_process_dead(os.getpid())

   atexit.register(_cleanup_metrics_files)
   ```

5. **`settings.py`** — keep `worker_metrics_port: int = 8001`
   unchanged. No new setting needed.

6. **`docker-compose.yml`** — update worker `command:` from
   `["python", "-m", "atlas20.api.worker.main"]` to
   `["python", "-m", "atlas20.api.worker"]`. Same for README.

7. **README.md** — line 77-78 update worker startup command:
   ```
   4. In another terminal, start the worker with
      `PYTHONPATH=src python -m atlas20.api.worker`.
   ```

**Test:** new `tests/test_worker_metrics_multiproc.py` — real-port E2E:
- Set `PROMETHEUS_MULTIPROC_DIR` to a tmp_path
- Pick an ephemeral free port (use `socket` to find one)
- Start `start_metrics_server(port)` in current process
- Call `_metrics.BACKTESTS_TOTAL.labels(status="completed").inc()` (counter writes to mmap)
- HTTP GET `http://127.0.0.1:{port}/metrics`
- Assert response contains `atlas20_backtests_total` with non-zero
  completed sample
- Teardown: `multiprocess.mark_process_dead(os.getpid())` + rmtree

If the multiprocess collector requires the env var be set BEFORE
prometheus_client imports, the test may need to spawn a subprocess.
Pragmatic alternative: monkeypatch the env, reload `_metrics`, and
verify the registry path. Document any constraint as a comment.

**Commit:** `fix(api): batch 17 r2 — worker /metrics aggregates run_one subprocess counters via PROMETHEUS_MULTIPROC_DIR`

---

## C2 — Real-port scrape test for worker /metrics

**Files:** consolidated into C1's `test_worker_metrics_multiproc.py`.

**Problem:** Existing `tests/test_worker_metrics.py` only mocks
`start_http_server`. Without a real scrape test, the C1 multiproc fix
itself could regress invisibly.

**Decision:** C1's test fulfils this. Keep existing mock tests; the
new real-port test is additive.

**Commit:** folded into C1 commit.

---

## W1 — Worker container HEALTHCHECK override

**Files:** `docker-compose.yml`.

**Problem (codex):** `Dockerfile:37` has image-level
`HEALTHCHECK ... curl http://127.0.0.1:8000/readyz`. The worker
container runs `python -m atlas20.api.worker` and binds 8001, not
8000. Healthcheck will fail forever; container shows unhealthy even
when processing jobs. Compose orchestration that depends on health
state will treat the worker as broken.

**Decision (Claude):** In `docker-compose.yml`, override the worker
service's healthcheck to hit its actual `/metrics` endpoint:

```yaml
  worker:
    # ... existing config
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8001/metrics"]
      interval: 30s
      timeout: 5s
      start_period: 30s
      retries: 3
```

`/metrics` is a sensible liveness probe for the worker — if the worker
binds and serves the multiproc registry, it's alive. No DB roundtrip
needed (the worker doesn't have a DB-backed readiness concept like
`/readyz`).

**Test:** docs only; manual verification with docker if available.

**Commit:** `fix(infra): batch 17 r2 — worker compose service overrides image HEALTHCHECK to scrape :8001/metrics`

---

## W2 — spawn.py port collision when multiple workers

**Files:** `src/atlas20/api/worker/spawn.py`, `src/atlas20/api/worker/main.py`, `tests/test_worker_metrics.py`.

**Problem (codex):** `spawn_workers(count=N)` launches N processes
that all call `start_metrics_server(8001)`. Second+ workers fail to
bind and crash, OR (worse) silently log and continue half-broken.

**Decision (Claude):** Make `start_metrics_server` tolerant of
`OSError: [WinError 10048]` / `EADDRINUSE`. With the multiproc setup,
only one process per container needs to expose /metrics — the rest
still write counters to the shared mmap dir which the first process's
collector aggregates. So:

```python
def start_metrics_server(port: int) -> None:
    global _metrics_server_started
    with _metrics_server_lock:
        if _metrics_server_started:
            return
        try:
            multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
            if multiproc_dir:
                from prometheus_client import CollectorRegistry, multiprocess
                registry = CollectorRegistry()
                multiprocess.MultiProcessCollector(registry)
                start_http_server(port, registry=registry)
            else:
                start_http_server(port)
            _metrics_server_started = True
            logger.info("worker prometheus /metrics listening on port %d (multiproc=%s)",
                        port, bool(multiproc_dir))
        except OSError as exc:
            # Another worker on the same host already bound the port.
            # With PROMETHEUS_MULTIPROC_DIR, that worker's collector
            # aggregates our writes too, so we proceed without our own
            # endpoint.
            _metrics_server_started = True
            logger.info(
                "worker prometheus /metrics port %d already bound (%s); "
                "this worker's counters will be aggregated by the bound "
                "process via PROMETHEUS_MULTIPROC_DIR=%s",
                port, exc, os.environ.get("PROMETHEUS_MULTIPROC_DIR"),
            )
```

**Test:** add `tests/test_worker_metrics.py::test_start_metrics_server_tolerates_port_in_use`
that monkeypatches `start_http_server` to raise OSError and verifies
`start_metrics_server` returns normally without raising and logs the
expected message.

**Commit:** `fix(api): batch 17 r2 — start_metrics_server tolerates EADDRINUSE under spawn.py multi-worker`

---

## W3 — docs/operations/logging.md API-vs-worker counter table

**Files:** `docs/operations/logging.md`.

**Problem (codex):** Section "Prometheus dual scrape targets" lists
`atlas20_report_generations_total` as worker-side. It's actually
API-side (incremented inside `/api/reports/generate` route handler at
`src/atlas20/api/services_report.py`). Also the histogram
`atlas20_backtest_duration_seconds` needs PromQL examples that handle
`_sum`/`_count`/`_bucket` aggregation, not just counter sum.

**Decision (Claude):** Rewrite the section to enumerate each metric
with its owning process. Use a table; add histogram PromQL examples.

```markdown
## Prometheus dual scrape targets (API + worker)

`prometheus_client` counters live in **per-process memory**. The API
process and worker process emit different metrics; each must be
scraped on its own endpoint.

| Metric                                  | Process | Notes                                                      |
| --------------------------------------- | ------- | ---------------------------------------------------------- |
| `atlas20_request_total{status,...}`     | API     | HTTP instrumentation via fastapi-instrumentator            |
| `atlas20_rate_limit_hits_total{route}`  | API     | slowapi handler                                            |
| `atlas20_report_generations_total{format,status}` | API | Incremented inside POST `/api/reports/generate` handler |
| `atlas20_backtests_total{status}`       | Worker  | Incremented in run_one subprocess; multiproc-aggregated   |
| `atlas20_backtest_duration_seconds`     | Worker  | Histogram; multiproc-aggregated                            |

Configure Prometheus with both scrape targets:

\`\`\`yaml
scrape_configs:
  - job_name: atlas20-api
    static_configs:
      - targets: ["atlas20-backend:8000"]
  - job_name: atlas20-worker
    static_configs:
      - targets: ["atlas20-worker:8001"]
\`\`\`

Counter queries that span both processes (none currently, but if you
add one):

\`\`\`promql
sum without (instance, job) (atlas20_backtests_total)
\`\`\`

Histogram queries — use `_sum` / `_count` / `_bucket` series, not the
base name:

\`\`\`promql
# p95 backtest duration over 1h, across all worker processes
histogram_quantile(
  0.95,
  sum by (le) (
    rate(atlas20_backtest_duration_seconds_bucket[1h])
  )
)
\`\`\`

Worker counters are aggregated across the run_one subprocess via
`PROMETHEUS_MULTIPROC_DIR` (see `src/atlas20/api/worker/__main__.py`).
The bootstrap is essential — without it every backtest completion is
silently dropped.
```

**Test:** docs-only.

**Commit:** `docs(infra): batch 17 r2 — corrected Prometheus scrape doc lists API vs worker counters and histogram PromQL`

---

## W4 — Shadow-install warning also runs on worker startup

**Files:** `src/atlas20/api/worker/main.py`.

**Problem (Claude):** `_warn_if_shadow_install` is wired in API
lifespan only. A worker launched with a stale non-editable install
still runs old code silently — same B11/B14/B16-shadowing failure
mode the API has, now in the worker path.

**Decision (Claude):** Import and call the API's
`_warn_if_shadow_install` from `worker.main.main()` (after
`setup_signal_handlers()`, before `start_metrics_server`). Lazy import
to avoid circular: `from atlas20.api.app import _warn_if_shadow_install`
inside the function body.

**Test:** existing `tests/test_app_lifespan_shadow.py` covers the
helper. Add `tests/test_worker_metrics.py::test_worker_main_invokes_shadow_warning`
that monkeypatches the helper and verifies `main()` invokes it once
(monkeypatch `start_metrics_server`, `_recover_on_startup`,
`WorkerQueue.claim_one` to return None, set `_shutdown_requested`
immediately so main loop exits).

**Commit:** `fix(api): batch 17 r2 — worker startup also emits shadow-install warning`

---

## I1 — README worker invocation updated

**Files:** `README.md`.

**Decision:** Folded into C1. Single commit message + README hunk in
C1's commit covers it.

---

## Procedure

5 atomic commits:

1. C1 + I1 (single commit) — worker multiproc + entry shim + readme + real-port test
2. W1 — worker compose healthcheck
3. W2 — start_metrics_server tolerates EADDRINUSE + test
4. W3 — logging.md doc rewrite
5. W4 — worker startup shadow warning + test

After each: `PYTHONPATH=src python -m pytest tests/ -x -q` green. After
all 5: `python scripts/verify_release.py` exit 0, `git diff --check
4f7c9f0..HEAD` clean.

**Final acceptance:**
- pytest: 351 → ~355+ (C1 adds 1-2, W2 adds 1, W4 adds 1)
- vitest: 161 unchanged
- verify_release exit 0

## Report back

- 5 commit hashes in order
- Final backend test count
- Any deviations from this plan (with Claude-decision justification)
- Confirmation that C1's real-port test PASSES (this is the round-2
  must-prove signal — if it fails the multiproc setup is still broken)
</TASK>