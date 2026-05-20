ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 7 reviewer findings. 1 Critical + 6 Warnings + 4 Info from both
Opus 4.7 and codex reviewers. Claude has decided fix direction for each.

EACH FIX = SEPARATE COMMIT. Run pytest after each.

## C1 — `next_btk_id` race condition (Critical, both reviewers)

File: `src/atlas20/api/repositories/runs_repo.py:84-92`

Two concurrent sessions can both return `btk_0149`, causing UNIQUE constraint
collision on insert.

**Fix:** retry loop on `IntegrityError`. Keep current MAX+1 logic but wrap
the create in try/except with up to 3 retries:

```python
from sqlalchemy.exc import IntegrityError

def create_with_unique_id(self, base_attrs: dict[str, Any]) -> Run:
    for attempt in range(3):
        run_id = self._compute_next_btk_id()
        try:
            run = Run(run_id=run_id, **base_attrs)
            self._s.add(run)
            self._s.flush()
            return run
        except IntegrityError:
            self._s.rollback()
            continue
    raise RuntimeError("could not allocate unique run_id after 3 attempts")
```

Refactor `register_new_backtest` in services.py to call this method.
Keep `next_btk_id()` as a public method but mark it deprecated for
non-concurrent paths only.

**Test:** add `tests/test_runs_repo_concurrency.py`:
- Use threading + ThreadPoolExecutor to invoke `create_with_unique_id`
  concurrently 10x.
- Assert all 10 inserts succeed and all run_ids are unique.
- Use a file-based SQLite (NOT :memory:) so threads share the connection.

**Commit:** `fix(api): batch 7 — atomic run_id allocation with retry loop`

## W1 — Timezone-aware datetime columns (both reviewers)

Files:
- `src/atlas20/api/db/models.py` — fields: `started_at`, `heartbeat_at`,
  `created_at` on Run; `generated_at` on ReportFile; `updated_at` on KvSetting;
  `created_at`, `expires_at` on IdempotencyKey.
- `src/atlas20/api/db/migrations/versions/20260520_0001_initial_schema.py`

**Fix:** add `sa_column` to each datetime field:

```python
from sqlalchemy import Column, DateTime

created_at: datetime = Field(
    default_factory=utc_now,
    sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
)
```

Update Alembic migration to use `sa.DateTime(timezone=True)` in `op.create_table`
calls. **Since no production data exists**, hand-edit the migration file —
do NOT generate a new revision.

**Test:** add `tests/test_datetime_tz_roundtrip.py`:
- Insert a Run with tz-aware created_at, commit, re-read, assert tzinfo is
  preserved (compare against `timezone.utc`).
- Same for ReportFile.generated_at and IdempotencyKey.expires_at.

**Commit:** `fix(api): batch 7 — timezone-aware datetime columns + roundtrip test`

## W2 — Alembic startup race (Opus only)

File: `src/atlas20/api/app.py:21-28` (lifespan)

Multi-worker uvicorn → N processes race on `command.upgrade(cfg, "head")`.

**Fix:** add `filelock` to deps. Wrap upgrade in FileLock:

```python
from contextlib import asynccontextmanager
from pathlib import Path

from filelock import FileLock

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    lock_path = Path(settings.db_url.replace("sqlite:///", "")).with_suffix(".alembic.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(lock_path), timeout=60):
        from alembic.config import Config
        from alembic import command
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
    yield
```

Add `filelock>=3.0` to `pyproject.toml`.

**Test:** add `tests/test_lifespan_startup.py`:
- Use `with TestClient(create_app()) as client:` on a tmp DB path.
- Assert tables exist after lifespan opens.
- (Note: testing the lock contention itself is OS-dependent; just verify
  the lock acquires + releases without crashing.)

**Commit:** `fix(api): batch 7 — file-lock alembic upgrade in lifespan`

## W3 — Backup hot-copy corruption (Opus only)

File: `src/atlas20/api/cli/backup.py:38-40`

Raw `tarfile.add` on in-flight SQLite can corrupt the tar.

**Fix:** use sqlite3 backup API to copy to a temp file first:

```python
import sqlite3
import tempfile

def _backup_sqlite_safely(db_path: Path) -> Path:
    """Copy SQLite DB to a temp file using the SQLite backup API."""
    fd, tmp = tempfile.mkstemp(suffix=".sqlite", prefix="atlas20-backup-")
    os.close(fd)
    tmp_path = Path(tmp)
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(tmp_path))
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    return tmp_path
```

Then add `tmp_path` to the tar with `arcname=db_path.name`. `unlink` the tmp
file in a finally.

Update `docs/operations/backup.md`:
- Document that backup is now hot-safe via sqlite3.backup().
- Keep "stop API before backup" as RECOMMENDED but not REQUIRED.

**Test:** update `tests/test_backup_cli.py` to assert the backup process
doesn't error when a long-running write transaction is open in another
connection (simulate with a background thread holding a transaction).

**Commit:** `fix(api): batch 7 — backup via sqlite3.backup() for hot-safe copy`

## W4 — btk_0142 detail synthesis post-seed (codex only)

File: `src/atlas20/api/services.py:191` (`get_run_detail`)

After seed inserts btk_0142, `get_run_detail("btk_0142")` reads from DB and
synthesizes kpi via `_derive_kpi_from_row`, which differs from canonical
`fallback_run_detail` for sortino, win_rate, calmar.

**Fix decision (Claude):** preserve canonical detail for `btk_0142`
regardless of DB state. In `get_run_detail`, check if `run_id == "btk_0142"`
FIRST and return `fallback_run_detail` (with current DB favorited state
overlaid). For all other IDs, derive from DB row as today.

```python
def get_run_detail(session: Session, run_id: str) -> RunDetailPayload | None:
    if run_id == mock_data.fallback_run_detail["run_id"]:
        canonical = deepcopy(mock_data.fallback_run_detail)
        db_row = RunsRepo(session).get(run_id)
        if db_row is not None:
            canonical["favorited"] = db_row.favorited
        return RunDetailPayload.model_validate(canonical)
    row = RunsRepo(session).get(run_id)
    if row is None:
        return None
    # ... synthesize for non-canonical ...
```

**Test:** update `tests/test_api_services.py:test_get_run_detail_returns_derived_kpi_for_listed_runs`
to assert canonical fields for btk_0142 (sortino, win_rate, calmar match
fallback_run_detail, NOT _derive_kpi_from_row's output).

**Commit:** `fix(api): batch 7 — preserve canonical run detail for btk_0142 after DB seed`

## W5 — Test gaps (codex)

Already addressed by C1 (concurrency), W1 (tz roundtrip), W2 (lifespan).

Additionally add:
- `tests/test_alembic_downgrade.py` — upgrade head, then downgrade base,
  assert all 4 tables dropped, then upgrade head again.

**Commit:** `test(api): batch 7 — alembic downgrade coverage`

## W6 — UTF-8 BOM on services.py (codex Info → upgraded by Claude)

File: `src/atlas20/api/services.py`

Strip UTF-8 BOM:
```bash
# verify first
file src/atlas20/api/services.py
# expect: UTF-8 Unicode (with BOM)
```

Codex should rewrite the file without BOM. Save as plain UTF-8.

No test needed.

**Commit:** `chore(api): batch 7 — strip UTF-8 BOM from services.py`

## I1 — Wire `purge_expired` (Opus)

File: `src/atlas20/api/repositories/idempotency_repo.py`

Currently dead code outside tests.

**Fix decision (Claude):** call `purge_expired` at end of `register_new_backtest`
(lazy cleanup pattern — every new backtest triggers a purge). This is cheap
and avoids needing a cron yet.

```python
# at end of register_new_backtest
IdempotencyRepo(session).purge_expired()
```

**Test:** add `tests/test_idempotency_lazy_purge.py` — register a backtest,
assert old idempotency rows are gone.

**Commit:** `feat(api): batch 7 — lazy purge_expired on backtest registration`

## I2 — Engine cache leak in tests (Opus)

File: `src/atlas20/api/repositories/_session.py:22` (`@lru_cache` on `_engine_for_url`)

Tests using tmp_path accumulate engines forever.

**Fix decision (Claude):** add an explicit `dispose_engine(db_url)` helper.
Update `tests/conftest.py` `db_session` fixture to call it in teardown.

```python
def dispose_engine(db_url: str) -> None:
    engine = _engine_for_url.cache_info()  # check if cached
    # ... use engine.dispose() if cached ...
```

Simpler: replace `lru_cache` with a module-level dict and provide a
`dispose_all_engines()` function. Test fixture calls it on teardown.

**Commit:** `refactor(api): batch 7 — engine cache with explicit disposal helper`

## I3 — Lifespan test coverage (Opus)

Addressed by W2's `test_lifespan_startup.py`. Mark as resolved.

## I5 — Consolidate `_run_from_seed_row` (Opus)

Files: `tests/conftest.py` + `src/atlas20/api/cli/seed.py`

Duplicate logic.

**Fix:** import the canonical version from `seed.py` into `conftest.py`. If
the CLI version isn't testable (e.g., does I/O), refactor to expose the
pure mapping function as `seed.run_from_seed_row(row: dict) -> Run`.

**Commit:** `refactor(api): batch 7 — share _run_from_seed_row between CLI and tests`

## Procedure

10 commits, in the order above (Critical → Warnings → Info). After EACH:
- `python -m pytest tests/ -x -q` must be green.
- After commit #8 (I2): also `cd apps/web && npm run test -- --run` — should
  remain 122.

## Final report

- 10 commit hashes (one per fix)
- Final backend test count (should be ~140 after adding regression tests)
- Frontend unchanged (122)
- Any deviations
- Net LOC delta
</TASK>
