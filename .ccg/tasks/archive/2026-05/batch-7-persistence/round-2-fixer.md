ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply 3 round-2 Info findings on Atlas20 Batch 7. Tight scope.

## Info #1 — `db_url` parsing is sqlite-only

File: `src/atlas20/api/app.py` (lifespan, around line 29)

**Current:** `lock_path = Path(settings.db_url.replace("sqlite:///", "")).with_suffix(".alembic.lock")`

Will misbehave on Postgres URLs.

**Fix:** use `sqlalchemy.engine.make_url`. Only take the file lock for
sqlite; Postgres has native advisory locks (out of scope here, just skip).

```python
from sqlalchemy.engine import make_url

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    url = make_url(settings.db_url)
    if url.drivername.startswith("sqlite") and url.database:
        db_path = Path(url.database)
        lock_path = db_path.with_suffix(".alembic.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path), timeout=60):
            cfg = Config("alembic.ini")
            command.upgrade(cfg, "head")
    else:
        # Postgres/MySQL: rely on alembic_version table + advisory locks (Batch 14 follow-up)
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
    yield
```

**Test:** add `tests/test_lifespan_non_sqlite.py` — monkeypatch
`settings.db_url` to a fake postgres URL (`postgresql://user@host/db`) and
assert lifespan boots without trying to create a lock file. (You can mock
`Config` and `command.upgrade` to avoid actual DB connection.)

**Commit:** `fix(api): batch 7 round 2 — parse db_url via sqlalchemy, skip filelock for non-sqlite`

## Info #2 — BEGIN IMMEDIATE shared-session comment

File: `src/atlas20/api/repositories/runs_repo.py` (around the
`_begin_immediate_for_sqlite` helper or `create_with_unique_id`)

**Fix:** add a code comment explaining the design:

```python
def _begin_immediate_for_sqlite(self) -> None:
    """Promote SQLite read-transaction to write-transaction immediately.

    Why: SQLite's default 'deferred' mode delays acquiring the reserved lock
    until first write, creating a TOCTOU window in MAX+1 id allocation.
    BEGIN IMMEDIATE acquires the lock at transaction start, serializing
    concurrent inserts across SEPARATE sessions/connections.

    Within a single session reused across calls, this helper short-circuits
    via in_transaction() — the outer scope already holds the write lock.
    The race we guard against is cross-session, not intra-session.
    """
    if self._s.in_transaction():
        return
    if self._s.bind and self._s.bind.dialect.name == "sqlite":
        self._s.execute(text("BEGIN IMMEDIATE"))
```

(Adjust to match actual function signature; this is a docs-only change.)

**No test needed.**

**Commit:** `docs(api): batch 7 round 2 — explain BEGIN IMMEDIATE in runs_repo`

## Info #3 — tz roundtrip test per-column

File: `tests/test_datetime_tz_roundtrip.py`

**Current:** asserts roundtrip on 3 tables but doesn't explicitly cover all
6 datetime columns.

**Fix:** extend test to assert each datetime column individually:
- `Run.created_at`, `Run.started_at`, `Run.heartbeat_at` (need to set
  started_at and heartbeat_at explicitly since they default None)
- `ReportFile.generated_at`
- `KvSetting.updated_at`
- `IdempotencyKey.created_at`, `IdempotencyKey.expires_at`

For each: write a tz-aware value (e.g., `datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)`),
commit, re-read in fresh session, assert `value.tzinfo == timezone.utc` and
`value == expected`.

**Commit:** `test(api): batch 7 round 2 — assert tz roundtrip per datetime column`

## Procedure

3 separate commits. After EACH:
- `python -m pytest tests/ -x -q` (expect 137 → 138 after info #1, then
  138, then 139 after info #3 if it adds extra cases)

## Report

- 3 commit hashes
- Final backend test count
- Any deviations
</TASK>
