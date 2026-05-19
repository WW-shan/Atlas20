# Batch 7 — Persistence (P1-P6 SQLite + SQLModel + Alembic)

## Goal

Add SQLite-backed persistence that can later be migrated to PostgreSQL.
Wire all run-mutating service-layer functions through a Repository pattern
behind FastAPI `Depends`.

Replaces the in-memory `mock_data.fallback_runs_*` mutation pattern. Mock
data stays as the *seed source*, not the live store.

## Scope (PR-sized, ~600 LOC + 25 tests)

### P1 — Selection + settings

**Decision (Claude):** SQLite + SQLModel 0.0.22+, Alembic 1.13+, async via
SQLModel's sync API wrapped in `run_in_threadpool` for now (move to
asyncpg if/when Postgres comes online). One DB connection per request via
FastAPI dependency.

**Add to `pyproject.toml`:**
- `sqlmodel>=0.0.22`
- `alembic>=1.13`
- (transitively brings `sqlalchemy>=2.0` and `pydantic>=2`)

**Extend `src/atlas20/api/settings.py`:**
- `db_url: str = "sqlite:///data/atlas20.sqlite"` — already exists from
  Batch 2, verify; if it's `db_url` keep it, otherwise rename.
- Add `backup_root: Path = Path("backups")` — where backup tarballs go.
- Add `backup_retention_days: int = 30`.

### P2 — Table schema

Create `src/atlas20/api/db/models.py` with **four SQLModel tables**:

```python
class Run(SQLModel, table=True):
    __tablename__ = "runs"
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True)  # e.g. "btk_0142"
    strategy: str
    strategy_family: str | None = None
    universe: str
    window_start: date
    window_end: date
    status: str = Field(index=True)  # queued|running|completed|failed
    return_pct: float | None = None
    sharpe: float | None = None
    max_dd: float | None = None
    duration_s: int | None = None
    eta_s: int | None = None
    spark: str | None = None  # JSON
    params: str | None = None  # JSON of BacktestConfig
    error: str | None = None
    worker_pid: int | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    requested_cancel: bool = False
    favorited: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class ReportFile(SQLModel, table=True):
    __tablename__ = "report_files"
    id: int | None = Field(default=None, primary_key=True)
    run_id: str | None = Field(index=True, foreign_key="runs.run_id", nullable=True)
    kind: str  # weekly|run|compare|universe
    path: str
    size_bytes: int
    sha256: str = Field(index=True)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KvSetting(SQLModel, table=True):
    __tablename__ = "kv_settings"
    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IdempotencyKey(SQLModel, table=True):
    __tablename__ = "idempotency_keys"
    key: str = Field(primary_key=True)
    method: str
    path: str
    response_json: str  # serialized response
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
```

All `datetime.now(timezone.utc)` calls must go through `atlas20.api._time`
(established in retro). Use `utc_now()` helper that returns `datetime` aware
(create it in `_time.py` if not yet present — alongside `utc_now_iso()`).

### P3 — Repository layer

Create `src/atlas20/api/repositories/`:

- `__init__.py` — exports `get_session`, `RunsRepo`, `ReportsRepo`,
  `IdempotencyRepo`, `KvRepo`.

- `_session.py`:
  ```python
  def get_engine(settings: Settings) -> Engine: ...
  def get_session() -> Session: ...  # FastAPI dependency, yields session
  ```

- `runs_repo.py`:
  ```python
  class RunsRepo:
      def __init__(self, session: Session): self._s = session
      def list(self, *, q="", chips=(), date_cutoff=None, page=1, page_size=14) -> tuple[list[Run], int]: ...
      def get(self, run_id: str) -> Run | None: ...
      def create(self, run: Run) -> Run: ...
      def update(self, run_id: str, **fields) -> Run | None: ...
      def toggle_favorite(self, run_id: str) -> Run | None: ...
      def list_queue(self) -> list[Run]: ...  # WHERE status IN ('queued','running')
      def next_btk_id(self) -> str: ...
  ```

- `reports_repo.py`:
  ```python
  class ReportsRepo:
      def list(self, *, sort="recent") -> list[ReportFile]: ...
      def get(self, report_id: int) -> ReportFile | None: ...
      def create(self, report: ReportFile) -> ReportFile: ...
      def by_run(self, run_id: str) -> list[ReportFile]: ...
  ```

- `idempotency_repo.py`:
  ```python
  class IdempotencyRepo:
      def get(self, key: str) -> IdempotencyKey | None: ...
      def store(self, key: str, method: str, path: str, response_json: str, ttl_seconds: int = 86400) -> None: ...
      def purge_expired(self) -> int: ...
  ```

- `kv_repo.py`:
  ```python
  class KvRepo:
      def get(self, key: str) -> str | None: ...
      def set(self, key: str, value: str) -> None: ...
  ```

### Service-layer integration

Migrate `src/atlas20/api/services.py`:

- `list_runs`, `get_run`, `toggle_run_favorite`, `list_runs_queue`,
  `register_new_backtest`, `get_run_detail` — all switch to read from
  `RunsRepo`.
- These functions now require a `session: Session` parameter.
- Update FastAPI routes in `src/atlas20/api/routes/runs.py` and
  `backtests.py` to inject `session: Session = Depends(get_session)` and
  pass through.
- For now `get_run_detail` still falls back to `mock_data.fallback_run_detail`
  for the canonical `btk_0142` if not in DB — this preserves the existing
  test contract until Batch 9 worker writes detail.

**Mock data is no longer mutated at runtime.** `fallback_runs_list` becomes
**immutable seed data** only used at first startup via the seed CLI.

### P4 — Alembic migrations

- `alembic init src/atlas20/api/db/migrations` — keep migrations in src tree
  for packaging.
- Configure `env.py` to use `Settings().db_url` and import SQLModel metadata
  from `atlas20.api.db.models`.
- Generate first migration: `alembic revision --autogenerate -m "initial schema"`.
- Startup hook in `app.py` (or a `lifespan` context):
  ```python
  @asynccontextmanager
  async def lifespan(app):
      from alembic.config import Config
      from alembic import command
      cfg = Config("alembic.ini")
      command.upgrade(cfg, "head")
      yield
  ```
- `alembic.ini` at repo root with sane defaults.

**Acceptance test:**
```bash
rm data/atlas20.sqlite
uvicorn atlas20.api.app:app  # must boot, create schema, run
```

### P5 — Seed CLI

Create `src/atlas20/api/cli/seed.py`:

```python
def main():
    settings = get_settings()
    engine = get_engine(settings)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        runs_repo = RunsRepo(session)
        if runs_repo.list(page_size=1)[1] > 0:
            print("DB already seeded, skipping")
            return
        for row in mock_data.fallback_runs_list:
            run = Run.model_validate({
                "run_id": row["run_id"],
                "strategy": row["strategy"],
                # ... map all RunRow fields ...
                "spark": json.dumps(row.get("spark") or []),
            })
            runs_repo.create(run)
        session.commit()
    print(f"Seeded {len(mock_data.fallback_runs_list)} runs")
```

Wire `python -m atlas20.api.seed` via `src/atlas20/api/seed/__main__.py`
or a console script in `pyproject.toml`.

### P6 — Backup

Create `src/atlas20/api/cli/backup.py`:

```python
def main():
    settings = get_settings()
    backup_root = settings.backup_root
    backup_root.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso().replace(":", "").replace("-", "")
    archive_path = backup_root / f"atlas20-{ts}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        db_path = _db_path_from_url(settings.db_url)
        if db_path and db_path.exists():
            tf.add(db_path, arcname=db_path.name)
        reports_dir = settings.report_root / "app_runs"
        if reports_dir.exists():
            tf.add(reports_dir, arcname="app_runs")
    print(f"Backup: {archive_path}")
    _purge_old(backup_root, retention_days=settings.backup_retention_days)
```

Wire as `python -m atlas20.api.backup`.

**RPO/RTO documentation:** add `docs/operations/backup.md` describing:
- Daily cron schedule (operator-driven for now; Batch 14 will wire)
- RPO: 24h (manual cron)
- RTO: minutes (untar + restart)

## Tests

Create `tests/test_db_*.py`:

1. `test_db_models.py` — schema creates without error in `:memory:` SQLite.
2. `test_runs_repo.py` — CRUD: create, list filters by status/family/q/date_range, paginate, toggle_favorite, next_btk_id increments.
3. `test_reports_repo.py` — CRUD + sort variants.
4. `test_idempotency_repo.py` — get returns None pre-store, get returns row post-store, expires_at honored.
5. `test_kv_repo.py` — get/set roundtrip.
6. `test_alembic_upgrade.py` — `command.upgrade(cfg, "head")` on a tmp DB
   creates expected tables.
7. `test_seed_cli.py` — running seed populates DB matches `mock_data.fallback_runs_list` count.
8. `test_backup_cli.py` — tarball exists post-run, contains DB file +
   app_runs/, old backups beyond retention are deleted.

Use `tmp_path` for DB file and override `ATLAS20_DB_URL` via monkeypatch.
Reset `get_settings.cache_clear()` between tests.

**Existing services tests** (test_api_services.py, test_api_routes.py)
must be updated to use a session fixture. Create `db_session` fixture in
`tests/conftest.py` that:
- creates in-memory engine
- runs `SQLModel.metadata.create_all`
- seeds with the same data as mock_data.fallback_runs_list
- yields session, rolls back after test

All 121 existing backend tests must still pass.

## Files expected

- `pyproject.toml` — add 2 deps
- `src/atlas20/api/settings.py` — backup_root + backup_retention_days
- `src/atlas20/api/_time.py` — add `utc_now()` aware datetime helper
- `src/atlas20/api/db/__init__.py`, `models.py`, `migrations/...`
- `src/atlas20/api/repositories/__init__.py`, `_session.py`, `runs_repo.py`,
  `reports_repo.py`, `idempotency_repo.py`, `kv_repo.py`
- `src/atlas20/api/cli/__init__.py`, `seed.py`, `backup.py`
- `src/atlas20/api/seed/__main__.py`, `src/atlas20/api/backup/__main__.py`
- `src/atlas20/api/services.py` — switch to repos
- `src/atlas20/api/routes/runs.py`, `backtests.py` — inject session
- `src/atlas20/api/app.py` — lifespan with alembic upgrade
- `alembic.ini`
- `docs/operations/backup.md`
- `tests/conftest.py` — db_session fixture
- `tests/test_db_*.py` (8 new files)
- ~600 LOC src + ~400 LOC tests

## Out of scope

- E2-E6 worker queue (Batch 9)
- R7 real data sources (Batch 13)
- User/auth tables (S4 is Batch 11)
- ALTER TABLE migrations (only initial schema this batch)

## Acceptance

- `python -m pytest tests/ -q` — green (~149 tests = 121 + 28 new)
- `rm data/atlas20.sqlite && uvicorn atlas20.api.app:app` — boots,
  creates schema, responds 200 on `/runs?date_range=all`
- `python -m atlas20.api.seed` — populates DB, idempotent on re-run
- `python -m atlas20.api.backup` — produces tarball in `backups/`
- `cd apps/web && npm run test -- --run` — still 122 (no frontend touch)
- No Critical findings from round-2 cross-validation

## Determinism

All datetime via `_time.utc_now()`. No `random` calls. Alembic migrations
have stable revision IDs (not autogenerated each run).
