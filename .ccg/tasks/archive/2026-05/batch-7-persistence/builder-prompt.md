ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Implement Atlas20 Batch 7 — Persistence (P1-P6 SQLite + SQLModel + Alembic).

Brief: `.ccg/tasks/batch-7-persistence/brief.md` (read it fully first).

Scope is large (~600 LOC src + ~400 LOC tests + alembic init). Take time.

Hard requirements:
1. Follow brief's algorithm + file layout EXACTLY. No scope creep.
2. All datetime via `atlas20.api._time` (existing module from retro batch).
   Add `utc_now()` helper if not yet there — return tz-aware datetime.
3. SQLModel models in `src/atlas20/api/db/models.py`. Tables exactly per
   brief (runs, report_files, kv_settings, idempotency_keys).
4. Repository pattern under `src/atlas20/api/repositories/` with one repo
   per aggregate. FastAPI `Depends(get_session)` injection.
5. Alembic init under `src/atlas20/api/db/migrations/`. First revision is
   "initial schema". Use `--autogenerate` but **commit the generated file**
   so revision IDs are stable.
6. Lifespan hook in `app.py` runs `alembic upgrade head` at startup.
7. Seed CLI: `python -m atlas20.api.seed` — idempotent, skips if DB has rows.
8. Backup CLI: `python -m atlas20.api.backup` — tar.gz of DB + app_runs/,
   30d rolling retention.
9. Existing 121 backend tests must still pass — update them to use the
   new `db_session` conftest fixture.
10. Add 8 new test files per brief.
11. Run `python -m pytest tests/ -x -q` after EACH major chunk
    (after models, after repos, after services, after CLIs).
12. Final acceptance: `rm data/atlas20.sqlite && python -m pytest tests/`
    must still be green (proves alembic creates schema from scratch).
13. Frontend unchanged — `cd apps/web && npm run test -- --run` still 122.

Apply your own internal review BEFORE the final commit. Commit message:
`feat(api): R7 batch 7 — P1-P6 SQLite persistence + alembic + seed/backup CLIs`

Report at the end:
- ✅/❌ PASS or FAIL
- Files created (count) / modified (count)
- Test count: backend before/after, frontend unchanged
- Alembic revision ID(s)
- Final commit hash
- Any deviations
</TASK>
