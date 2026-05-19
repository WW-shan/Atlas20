ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Implement Atlas20 Batch 9 — Worker Queue (E2/E3/E4/E5/E6/E8 + C4).

Brief: `.ccg/tasks/batch-9-worker-queue/brief.md` (read fully first).

This is the LARGEST batch in the roadmap. Real subprocess-based backtest
execution with timeout/cancel/recovery. ~800 LOC src + ~600 LOC tests.

Hard requirements:
1. Follow brief Scope exactly. NO scope creep.
2. NEW MODULE `src/atlas20/api/worker/` with main/run_one/queue/recovery/__main__.
3. Worker polls DB for `status='queued'` runs via BEGIN IMMEDIATE serialized
   claim (`runs_repo.create_with_unique_id` retry pattern reused).
4. Subprocess timeout via `proc.communicate(timeout=...)`.
5. Heartbeat thread updates `heartbeat_at` every 10s; checks
   `requested_cancel` flag.
6. SIGTERM cancellation via `proc.terminate()` (cross-platform).
7. Restart recovery: `recover_stale_runs(stale_after_seconds=60)` called
   from lifespan (in addition to existing alembic upgrade).
8. POST /api/runs/{run_id}/cancel route with 404/409/202 semantics.
9. `register_new_backtest` writes to DB only — NO inline execution.
   Subprocess will pick it up.
10. Tests MUST mock `run_research_pipeline` via `ATLAS20_WORKER_MOCK=1`
    env var path that synthesizes minimal artifacts in <1s.
11. After each major chunk run `python -m pytest tests/ -x -q` and confirm.
12. Frontend untouched — `apps/web` test count stays 122.
13. Lint + typecheck still clean.
14. Final commit: `feat(api): R9 batch 9 — worker queue + subprocess execution + cancel + restart recovery`

Apply your own internal review before final commit.

Report:
- ✅/❌ PASS or FAIL
- Files created (count) / modified (count)
- Backend test count (was 168, expect ~198)
- Frontend test count (must stay 122)
- Acceptance smoke verified? (worker boots, subprocess mock executes)
- Final commit hash
- Any deviations
</TASK>
