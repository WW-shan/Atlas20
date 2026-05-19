# Batch 9 — Worker Queue (E2-E6/E8 + C4)

## Goal

Make backtests **actually execute** in background workers, write results
to `reports/app_runs/{run_id}/`, support timeouts/cancel/restart recovery.

Replaces the in-memory `register_new_backtest` synchronous mock with real
async execution via subprocess.

## Scope (~800 LOC + 30 tests)

### E2 — DB-backed job queue

**Decision (Claude):** Simple long-polling worker. No Redis, no Celery.
SQLite is the queue, `runs.status='queued'` rows are pending jobs.

**New files:**
- `src/atlas20/api/worker/__init__.py`
- `src/atlas20/api/worker/main.py` — long-running poll loop
- `src/atlas20/api/worker/run_one.py` — subprocess entry per run
- `src/atlas20/api/worker/queue.py` — claim/release logic

**Worker main loop** (`main.py`):
```python
def main():
    settings = get_settings()
    n_workers = int(os.environ.get("ATLAS20_WORKERS", "2"))
    setup_signal_handlers()
    while not _shutdown_requested:
        with session_scope() as session:
            claimed = WorkerQueue(session).claim_one()
            if claimed is None:
                time.sleep(2.0)
                continue
        # claimed is a Run with status='running', worker_pid set
        _execute_run(claimed.run_id, settings)
```

**Claim logic** (`queue.py`):
```python
def claim_one(self) -> Run | None:
    """Atomically claim a queued run. Returns None if none available."""
    self._begin_immediate_for_sqlite()
    candidate = self._s.exec(
        select(Run)
        .where(Run.status == "queued")
        .order_by(Run.created_at.asc())
        .limit(1)
    ).first()
    if candidate is None:
        return None
    candidate.status = "running"
    candidate.worker_pid = os.getpid()
    candidate.started_at = utc_now()
    candidate.heartbeat_at = utc_now()
    self._s.add(candidate)
    self._s.commit()
    return candidate
```

**Heartbeat:** worker spawns a thread that updates `heartbeat_at` every 10s
while subprocess is running.

**Cancel check:** heartbeat thread also reads `requested_cancel`; if True,
sends `SIGTERM` to subprocess.

### E3 — Write artifacts atomically

**Per-run output layout:**
```
reports/app_runs/{run_id}.tmp/
  summary.csv          # per-strategy KPIs from this run
  equity_curve.csv     # date × strategy_name
  daily_returns.csv    # date × strategy_name
  weights/{strategy}.csv  # date × asset
  selection_history.csv   # rebalance_date, coin_id, rank, weight
  manifest.json           # sha256 of each file, code_commit, config_hash
  params.json             # original BacktestConfig dump
```

On completion, atomic rename `{run_id}.tmp` → `{run_id}`. Reuses Batch 1's
`_publish_report_dir` pattern.

Subprocess `run_one.py`:
1. Load run from DB by `run_id`.
2. Deserialize `run.params` JSON → `BacktestConfig`.
3. Call `to_research_config(api_config, settings)`.
4. Override `research_config.paths.reports_dir = settings.report_root / "app_runs" / f"{run_id}.tmp"`.
5. Call existing `run_research_pipeline(research_config)`.
6. Compute manifest (sha256 of all output files + git rev-parse HEAD).
7. Update `runs` row: `status='completed'`, `return_pct`/`sharpe`/`max_dd`
   from summary, `duration_s` = elapsed, `heartbeat_at=None`.
8. Atomic rename tmp → final.

On uncaught exception:
- `status='failed'`, `error=str(exc)[:1000]`, leave `.tmp/` for debug.

### E4 — Timeout via subprocess

In `worker/main.py:_execute_run`:
```python
proc = subprocess.Popen(
    [sys.executable, "-m", "atlas20.api.worker.run_one", run_id],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
try:
    stdout, stderr = proc.communicate(timeout=settings.run_timeout_seconds)
except subprocess.TimeoutExpired:
    proc.kill()
    proc.communicate()  # drain
    # worker marks status=failed, error="timeout"
```

Default `run_timeout_seconds = 1800` (30 min). Configurable via settings.

### E5 — Worker pool concurrency

Run `N` worker processes (env `ATLAS20_WORKERS=2`). Each is independent;
they compete on the queue claim transaction (BEGIN IMMEDIATE serializes).

`docker-compose.yml` (Batch 14) will run N replicas. For local dev:
```bash
python -m atlas20.api.worker.main &  # worker 1
python -m atlas20.api.worker.main &  # worker 2
```

Add `src/atlas20/api/worker/spawn.py`: utility to fork N workers as
child processes for tests + manual launch.

### E6 — Cancel via SIGTERM

**New route:** `POST /api/runs/{run_id}/cancel`

```python
@router.post("/{run_id}/cancel", status_code=202)
def cancel_run(run_id: str, session: Session = Depends(get_session)):
    repo = RunsRepo(session)
    run = repo.get(run_id)
    if run is None:
        raise HTTPException(404)
    if run.status not in {"queued", "running"}:
        raise HTTPException(409, f"cannot cancel {run.status} run")
    repo.update(run_id, requested_cancel=True)
    return {"run_id": run_id, "requested_cancel": True}
```

Worker heartbeat thread reads `requested_cancel`; if True:
1. Send `SIGTERM` to subprocess (cross-platform: use `proc.terminate()`).
2. Wait up to 5s; if still alive, `proc.kill()`.
3. Mark `status='cancelled'`, `error='cancelled by user'`.

**Test:** start a slow `time.sleep(30)` subprocess, post cancel, assert
status `cancelled` within 6s.

### E8 — Restart recovery

In `lifespan` (after alembic upgrade):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... alembic upgrade ...
    with session_scope() as session:
        recovered = recover_stale_runs(session, stale_after_seconds=60)
        if recovered:
            logger.info("Recovered %d stale running runs", recovered)
    yield
```

`recover_stale_runs`:
- Find `status='running'` with `heartbeat_at < now - 60s` (or NULL).
- Set `status='failed'`, `error='worker died — heartbeat stale'`.

Worker also does this on startup (different scope — only its own PID
that no longer exists).

### C4 — register_new_backtest writes to runs (DB)

Already partially done in Batch 7. Verify:
- `register_new_backtest` inserts into `runs` table with `status='queued'`
- `params` JSON column contains the original BacktestConfig dump
- Mock data `fallback_runs_queue` is no longer mutated at runtime

If still mutated → remove that mutation.

## Tests

`tests/test_worker_queue.py` (~12 tests):
1. `test_claim_one_returns_oldest_queued_run`
2. `test_claim_one_skips_already_running`
3. `test_claim_one_returns_none_when_empty`
4. `test_claim_marks_status_running_and_sets_worker_pid`
5. `test_concurrent_claim_from_two_workers_returns_different_runs` (threads)
6. `test_heartbeat_thread_updates_heartbeat_at`
7. `test_cancel_sends_sigterm` (mock subprocess)
8. `test_timeout_kills_subprocess`
9. `test_completed_run_updates_status_and_metrics`
10. `test_failed_subprocess_marks_status_failed_with_error`
11. `test_recover_stale_runs_marks_failed`
12. `test_recover_stale_runs_ignores_fresh_heartbeats`

`tests/test_worker_run_one.py` (~8 tests):
- Subprocess entry happy path (mock `run_research_pipeline`)
- Subprocess writes atomic artifacts (tmp → final rename)
- Subprocess handles missing run_id gracefully (exit 1, no DB change)
- Subprocess records sha256 manifest

`tests/test_cancel_route.py` (~5 tests):
- 404 for non-existent run
- 409 for already-completed run
- 202 for queued run
- 202 for running run
- Cancellation sets requested_cancel=True in DB

`tests/test_restart_recovery.py` (~5 tests):
- Stale running (no heartbeat) → failed
- Fresh running (recent heartbeat) → untouched
- Queued runs → untouched
- Multiple stales → all recovered
- Lifespan calls recover_stale_runs

## Files expected

NEW:
- `src/atlas20/api/worker/__init__.py`
- `src/atlas20/api/worker/main.py` (~120 LOC)
- `src/atlas20/api/worker/run_one.py` (~150 LOC)
- `src/atlas20/api/worker/queue.py` (~80 LOC)
- `src/atlas20/api/worker/recovery.py` (~50 LOC)
- `src/atlas20/api/worker/__main__.py` (entry: forwards to main)
- `tests/test_worker_queue.py`
- `tests/test_worker_run_one.py`
- `tests/test_cancel_route.py`
- `tests/test_restart_recovery.py`
- `tests/conftest.py` — `worker_subprocess` fixture for integration tests

MODIFIED:
- `src/atlas20/api/settings.py` — `run_timeout_seconds`, `worker_poll_interval_seconds`
- `src/atlas20/api/app.py` — lifespan calls `recover_stale_runs`
- `src/atlas20/api/routes/runs.py` — POST /{run_id}/cancel
- `src/atlas20/api/services.py` — register_new_backtest writes to DB only,
  no inline execution
- `src/atlas20/api/repositories/runs_repo.py` — add `update_metrics_from_completion`
  helper (writes status, return_pct, sharpe, etc. atomically)
- `pyproject.toml` — no new deps (subprocess is stdlib)

## Out of scope

- Real backtest engine optimization (uses existing `run_research_pipeline`)
- Worker autoscaling
- Distributed workers (Redis/Celery) — MVP is single-machine
- Live progress events (SSE/WebSocket) — Batch 13+
- Frontend changes — the `/runs/{id}` polling already works from Batch 6

## Acceptance

- `python -m pytest tests/ -q` → ~198 passed (168 + ~30 new)
- `python -m atlas20.api.worker.main` — starts, polls, processes runs
- Manual smoke:
  1. `python -m atlas20.api.seed`
  2. `uvicorn atlas20.api.app:app`
  3. `python -m atlas20.api.worker.main &`
  4. POST a backtest → status moves queued → running → completed within minutes
  5. Files appear at `reports/app_runs/btk_NNNN/`
- POST cancel on a running run → status `cancelled` within 5s
- kill -9 worker mid-run → next lifespan startup recovers status `failed`

## Determinism

`atlas20.api._time.utc_now()` everywhere. `os.urandom` for any needed
unique IDs (no random module). Subprocess inherits parent env so settings
flow through.

## Implementation notes

- The actual backtest execution can take minutes. Tests MUST mock
  `run_research_pipeline` or use a `--mock` flag in `run_one.py` to
  short-circuit with synthesized output. Use a `ATLAS20_WORKER_MOCK=1` env
  var path that writes mock artifacts in <1s.
- Cross-platform SIGTERM: `proc.terminate()` works on Windows + POSIX.
- File locks for worker: not needed since DB transaction is the sync point.
- The `.tmp` dir cleanup on failure: keep for debug, don't auto-delete.
- Heartbeat thread must use a separate Session — don't share with main
  worker thread.
