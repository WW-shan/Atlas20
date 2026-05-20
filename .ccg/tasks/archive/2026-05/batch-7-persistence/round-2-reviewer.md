ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\reviewer.md
<TASK>
Round-2 independent validation of Atlas20 Batch 7 reviewer fixes.

10 commits in scope, range `f22771b..HEAD`:

```
3de75af refactor(api): batch 7 — share _run_from_seed_row between CLI and tests
2fe67fd refactor(api): batch 7 — engine cache with explicit disposal helper
014efae feat(api): batch 7 — lazy purge_expired on backtest registration
383a4e9 chore(api): batch 7 — strip UTF-8 BOM from services.py
c73ece2 test(api): batch 7 — alembic downgrade coverage
ed111d6 fix(api): batch 7 — preserve canonical run detail for btk_0142 after DB seed
0174ba3 fix(api): batch 7 — backup via sqlite3.backup() for hot-safe copy
8344958 fix(api): batch 7 — file-lock alembic upgrade in lifespan
6f6f40b fix(api): batch 7 — timezone-aware datetime columns + roundtrip test
7f9c762 fix(api): batch 7 — atomic run_id allocation with retry loop
```

These address findings from round-1 reviewers:
- Codex round 1: REQUEST_CHANGES 78/100, 1 Critical (next_btk_id race) + 3 Warning
- Opus round 1: REQUEST_CHANGES 84/100, 4 Warning + 5 Info

VALIDATION DIMENSIONS:

For each commit verify: (a) the original finding is genuinely resolved
with code AND test coverage; (b) no regression in existing 132 tests.

1. **C1 atomic run_id (7f9c762)** — verify `next_btk_id` or new
   `create_with_unique_id` has retry-on-IntegrityError. Codex noted it
   also added `BEGIN IMMEDIATE` before MAX+1 for SQLite — confirm that's
   safe and doesn't deadlock. Verify the concurrency test uses file SQLite
   (not :memory:) and 10 threads.

2. **W1 tz-aware datetime (6f6f40b)** — codex noted SQLite drops tzinfo
   even with `DateTime(timezone=True)`, so added a `UtcDateTime` adapter.
   Verify:
   - The custom type properly assigns UTC on read.
   - All 6 datetime columns (Run.created_at, started_at, heartbeat_at;
     ReportFile.generated_at; KvSetting.updated_at; IdempotencyKey.created_at,
     expires_at) use the adapter.
   - Roundtrip test asserts tzinfo == timezone.utc after re-read.
   - Migration was hand-edited (no new revision).

3. **W2 filelock alembic (8344958)** — verify `filelock` added to pyproject;
   lifespan wraps `command.upgrade` with FileLock; lock path is in DB dir.
   Verify the lifespan test uses `with TestClient(create_app()) as client:`.

4. **W3 sqlite3.backup (0174ba3)** — verify backup CLI uses
   `sqlite3.connect(src).backup(dst)` to temp file before tar; temp file
   cleaned up in finally. Verify docs/operations/backup.md updated.

5. **W4 canonical btk_0142 (ed111d6)** — verify `get_run_detail`
   short-circuits for `btk_0142` and returns deepcopy of fallback_run_detail
   with DB favorited overlaid. Verify test asserts canonical sortino/win_rate/calmar.

6. **W5 alembic downgrade test (c73ece2)** — verify test upgrades head,
   downgrades base, asserts tables absent, re-upgrades head.

7. **W6 BOM strip (383a4e9)** — `file src/atlas20/api/services.py` should
   no longer report BOM. Or `head -c 3 services.py | hexdump` should not
   show `ef bb bf`.

8. **I1 lazy purge_expired (014efae)** — verify call site in
   register_new_backtest. Verify test seeds an expired row then registers
   a new backtest and asserts the expired row is gone.

9. **I2 engine cache dispose (2fe67fd)** — verify cache is no longer
   `@lru_cache` (or has explicit disposal). conftest `db_session` fixture
   teardown calls dispose.

10. **I5 _run_from_seed_row shared (3de75af)** — verify CLI `seed.py`
    exports the function and conftest imports it from there.

ADDITIONALLY check for new issues introduced:
- New deps `filelock` added but not in dev/test deps?
- `UtcDateTime` adapter naming consistent with project conventions?
- Any commits leave dead imports or unused vars?
- Frontend unchanged (122 tests, no apps/web/ touched)?

Run yourself:
- `python -m pytest tests/ -x -q` (expect 137)
- `cd apps/web && npm run test -- --run` (expect 122)
- `cd apps/web && npm run typecheck` (clean)
- `cd apps/web && npm run lint` (0 warnings)

AUTHORITY: apply additional fixes ONLY for new Critical/Warning. Commit:
`fix(api): batch 7 round 2 — <one-line summary>`.

Do NOT touch `.ccg/tasks/review-r3-premium-redesign/.turns.json`.

REPORT FORMAT:
- Score X/100
- Each original finding: ✅ RESOLVED / ❌ STILL OPEN
- New findings: Critical / Warning / Info
- Fixes applied: commit hashes or 'none'
- Final test count
- Verdict: APPROVE / REQUEST_CHANGES

If no new findings AND all 10 originals resolved → APPROVE.

Keep under 1000 words.
</TASK>
