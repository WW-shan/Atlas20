ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-1 independent review of Atlas20 Batch 7 persistence.

TARGET: commit `f22771b` — "feat(api): R7 batch 7 — P1-P6 SQLite persistence + alembic + seed/backup CLIs"

BRIEF: `.ccg/tasks/batch-7-persistence/brief.md`

SCOPE: This is the heaviest batch so far. Sets up the persistence layer that
Batches 9-10 depend on. Get this right.

DIFF: `git diff HEAD~1 HEAD --stat` then per-file `git diff` on the
important ones:
- `src/atlas20/api/db/models.py`
- `src/atlas20/api/db/migrations/versions/*.py`
- `src/atlas20/api/repositories/_session.py`
- `src/atlas20/api/repositories/runs_repo.py`
- `src/atlas20/api/repositories/reports_repo.py`
- `src/atlas20/api/repositories/idempotency_repo.py`
- `src/atlas20/api/repositories/kv_repo.py`
- `src/atlas20/api/cli/seed.py`
- `src/atlas20/api/cli/backup.py`
- `src/atlas20/api/services.py`
- `src/atlas20/api/routes/runs.py`
- `src/atlas20/api/routes/backtests.py`
- `src/atlas20/api/app.py` (lifespan)
- `alembic.ini`

REVIEW DIMENSIONS:

1. **Schema correctness vs brief P2:**
   - `runs` table has all 21 columns per brief
   - `report_files` has FK to `runs.run_id` nullable
   - `kv_settings` is PK on key
   - `idempotency_keys` has TTL via `expires_at`
   - Indexes on `run_id`, `status`, `created_at`, `sha256`
   - Types: dates as DATE, timestamps as DATETIME with tz

2. **Repository correctness:**
   - `RunsRepo.list` honors q/chips/date_cutoff/page/page_size — matches
     the existing `list_runs` filter semantics from services.py history
   - `next_btk_id` is atomic (transaction-safe)
   - `toggle_favorite` correctly flips on a single row
   - No N+1 queries
   - Session is scoped per-request, no leaks

3. **Alembic correctness:**
   - First migration creates ALL 4 tables
   - Revision ID stable (committed file)
   - `env.py` reads `Settings().db_url` properly
   - Downgrade reverses cleanly (test if downgrade exists)
   - Lifespan in `app.py` calls `upgrade head` once at startup

4. **Service-layer migration:**
   - All run-mutating functions take `session: Session` param now
   - Routes inject `Depends(get_session)` and pass through
   - Mock data is no longer mutated at runtime
   - `get_run_detail` fallback to `mock_data.fallback_run_detail` for
     `btk_0142` preserved (brief explicitly required this)

5. **Seed CLI:**
   - Idempotent on re-run (skips if rows exist)
   - Maps all RunRow fields correctly (including JSON spark/params)
   - `python -m atlas20.api.seed` works as module entry

6. **Backup CLI:**
   - tar.gz includes DB + app_runs/
   - 30d retention purges old backups
   - Timestamps in filename are sortable
   - `_db_path_from_url` handles `sqlite:///` correctly (relative + absolute)

7. **Determinism + invariants:**
   - All `datetime.now()` via `_time.utc_now()` — grep for raw `datetime.now`
     outside `_time.py`
   - No raw `import random`
   - SQLModel models use timezone-aware datetimes

8. **Test coverage:**
   - 11 new tests added (132 - 121)
   - Each repo has CRUD tests
   - Alembic upgrade test on fresh tmp DB
   - Seed + Backup CLI tests
   - `db_session` fixture in conftest.py works for existing tests

9. **Documentation:**
   - `docs/operations/backup.md` exists per brief
   - RPO/RTO documented

10. **Run pytest yourself:** `python -m pytest tests/ -x -q` (expect 132)

AUTHORITY: Apply fixes directly for Critical/Warning. Commit as:
`fix(api): batch 7 reviewer pass — <one-line summary>`. Each fix = separate commit.

Do NOT touch `.ccg/tasks/review-r3-premium-redesign/.turns.json` or any
non-batch-7 file.

REPORT FORMAT:
- Score X/100
- Critical: list or 'none'
- Warning: list or 'none'
- Info: list
- Fixes applied: commit hashes or 'none'
- Final test count
- Verdict: APPROVE / REQUEST_CHANGES

Keep under 1000 words.
</TASK>
