ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-1 review of Atlas20 Batch 9 — Worker Queue.

TARGET: commit `12567f5` — "feat(api): R9 batch 9 — worker queue + subprocess execution + cancel + restart recovery"

BRIEF: `.ccg/tasks/batch-9-worker-queue/brief.md` (likely archived under `.ccg/tasks/archive/`)

SCOPE: This is the LARGEST batch (~800 LOC src + ~600 LOC tests). Real
subprocess-based backtest execution. High failure surface area.

DIFF:
- `git show 12567f5 --stat`
- Per-file dive into the new worker module:
  - `src/atlas20/api/worker/main.py`
  - `src/atlas20/api/worker/run_one.py`
  - `src/atlas20/api/worker/queue.py`
  - `src/atlas20/api/worker/recovery.py`
  - `src/atlas20/api/worker/spawn.py`
  - `src/atlas20/api/worker/__main__.py`
  - `src/atlas20/api/app.py` (lifespan recovery)
  - `src/atlas20/api/routes/runs.py` (POST cancel)
  - `src/atlas20/api/services.py` (register_new_backtest, no inline execution)
  - `src/atlas20/api/repositories/runs_repo.py` (update_metrics_from_completion)
  - `src/atlas20/api/settings.py` (run_timeout_seconds, worker_poll_interval_seconds)

REVIEW DIMENSIONS:

1. **E2 Queue correctness:**
   - `claim_one` is atomic — uses BEGIN IMMEDIATE before SELECT/UPDATE.
   - Concurrent claims from 2 workers don't double-claim (verify test).
   - Empty queue returns None without blocking.

2. **E3 Atomic artifact write:**
   - `run_one.py` writes to `reports/app_runs/{run_id}.tmp/` first
   - `os.replace` (atomic on POSIX + Windows) rename to final dir
   - On failure: tmp left for debug, no partial final dir
   - Manifest.json contains sha256 of each artifact + code_commit (git rev-parse HEAD)
   - params.json contains original BacktestConfig dump

4. **E4 Timeout:**
   - `proc.communicate(timeout=settings.run_timeout_seconds)` (default 1800)
   - On TimeoutExpired: `proc.kill()` then drain
   - Status → 'failed', error → 'timeout' (or similar)
   - Test exercises actual timeout path (likely with smaller timeout)

5. **E5 Worker pool:**
   - `ATLAS20_WORKERS` env read; defaults to 2
   - `spawn.py` forks N processes for tests/dev
   - Tests verify 2 workers claim different runs

6. **E6 Cancel:**
   - POST /api/runs/{run_id}/cancel returns 404 / 409 / 202 per brief
   - Heartbeat thread reads `requested_cancel`; on True → SIGTERM subprocess
   - 5s grace then SIGKILL
   - Worker marks status='cancelled'
   - Cross-platform: `proc.terminate()` works on Windows

7. **E8 Restart recovery:**
   - Lifespan calls `recover_stale_runs(stale_after_seconds=60)` AFTER alembic upgrade
   - Stale = status='running' AND (heartbeat_at < now-60s OR heartbeat_at IS NULL)
   - Recovered → status='failed', error='worker died — heartbeat stale'
   - Fresh heartbeats left untouched

8. **C4 register_new_backtest:**
   - Writes to DB with status='queued' (NOT 'running' or inline execution)
   - mock_data fallback_runs_queue no longer mutated at runtime
   - `params` JSON serializes BacktestConfig faithfully

9. **Settings:**
   - `run_timeout_seconds: int = 1800`
   - `worker_poll_interval_seconds: float = 2.0`
   - `worker_heartbeat_interval_seconds: float = 10.0` (or similar)

10. **Status schema:**
   - Codex deviation: added `cancelled` to status literals. Verify this is
     done at all schema sites: RunStatusEnum, mock data, frontend type.

11. **Subprocess isolation:**
    - run_one.py is the subprocess entry; reads run_id arg from sys.argv
    - Opens fresh DB session (NOT the parent's session)
    - Loads run.params → BacktestConfig
    - Calls to_research_config → run_research_pipeline
    - Updates DB on completion via RunsRepo (new session)

12. **Mock path for tests:**
    - `ATLAS20_WORKER_MOCK=1` short-circuits real pipeline
    - Writes minimal mock artifacts (summary.csv, manifest.json, etc.) in <1s
    - Used by all worker integration tests

13. **Heartbeat thread:**
    - Separate Session — does NOT share with main worker thread
    - Updates every 10s while subprocess running
    - Daemon thread (dies with worker)
    - Catches DB errors gracefully (worker should keep running)

14. **Test coverage** (~30 tests claimed):
    - test_worker_queue.py: 12+ tests
    - test_worker_run_one.py: 8+ tests
    - test_cancel_route.py: 5+ tests
    - test_restart_recovery.py: 5+ tests
    - Concurrent claim test uses threading + file SQLite
    - Subprocess tests use ATLAS20_WORKER_MOCK
    - Cancel test asserts status flips to 'cancelled' within 5s

Watch for:
- Race conditions in heartbeat update vs cancel signal
- DB connection leaks across subprocess boundary
- Worker process leaks (not cleaned up between tests)
- Cross-platform issues (proc.terminate behaves differently on Windows)
- Missing cleanup of .tmp dirs in test teardown
- `cancelled` status missing from places that filter by status

Run yourself:
- `python -m pytest tests/ -x -q` (expect 198 passed)
- `cd apps/web && npm run test -- --run` (expect 122)
- `cd apps/web && npm run lint` clean
- `cd apps/web && npm run typecheck` clean

AUTHORITY: apply fixes for Critical/Warning. Commit:
`fix(api): batch 9 reviewer pass — <one-line summary>`. Each fix separate.

REPORT:
- Score X/100
- Critical / Warning / Info
- Fixes applied: commits or 'none'
- Final test count
- Verdict: APPROVE / REQUEST_CHANGES

Keep under 1200 words.
</TASK>
