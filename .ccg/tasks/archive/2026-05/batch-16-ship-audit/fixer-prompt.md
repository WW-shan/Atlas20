ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Atlas20 FINAL ship-gate audit findings. Three deep reviewers (Opus security,
Opus architecture, Codex pragmatic) merged + Claude manual sweep.

**21 findings (7 Critical + 11 Warning + 3 Info).** User explicit: "不要有任何问题"
(no problems remain) — fix ALL.

**Each = separate commit.** Run pytest + npm test + verify_release.py after each.
Frontend stays 157; backend climbs 332 → ~342.

Range: starts from current HEAD `3bfb2df`.

---

## CRITICAL (1-7)

### C1 — Dockerfile: alembic.ini + migrations + config/ missing from runtime image

**Files:** `Dockerfile`, possibly `alembic.ini`.

**Problem (Opus sec + Codex smoke-verified):** Runtime stage only `COPY docs ./docs`.
At startup `app.py:73 Config("alembic.ini")` resolves to `/app/alembic.ini` → FileNotFoundError → uvicorn never serves. Codex independently reproduced via clean-cwd smoke probe; exit 3 with "No 'script_location' key found in configuration."

Even after alembic fix: `config_adapter.py:54-61` reads `config/base.yaml` from `settings.project_root`. Docker doesn't copy `config/` and compose doesn't set `ATLAS20_PROJECT_ROOT`. Every backtest in container will fail.

**Decision (Claude):**

```dockerfile
# Builder stage (unchanged):
COPY pyproject.toml README.md ./
COPY src ./src

# Runtime stage — add:
COPY --chown=atlas:atlas alembic.ini ./alembic.ini
COPY --chown=atlas:atlas src/atlas20/api/db/migrations ./migrations
COPY --chown=atlas:atlas config ./config
COPY --chown=atlas:atlas docs ./docs

# alembic.ini script_location must be relative to /app:
# Update alembic.ini line 2: `script_location = migrations`
```

Update `alembic.ini` `script_location` from `src/atlas20/api/db/migrations` to `migrations` so it works in both repo and container (repo has `migrations` available too via symlink OR we keep dual support via env override).

ACTUALLY cleaner approach: keep `alembic.ini` script_location as-is for repo dev, but in Docker COPY the migrations to the same relative path. So in Dockerfile:

```dockerfile
COPY --chown=atlas:atlas alembic.ini ./alembic.ini
COPY --chown=atlas:atlas src/atlas20/api/db/migrations ./src/atlas20/api/db/migrations
COPY --chown=atlas:atlas config ./config
```

This preserves the script_location path string. Verify with `docker build` if daemon available; otherwise note as ops-attention.

Update `docker-compose.yml` to set `ATLAS20_PROJECT_ROOT: /app` explicitly so config_adapter knows where to look.

**Test:** add `tests/test_packaged_startup.py` that imports `atlas20.api.app:create_app` from a clean cwd (chdir to tmp_path, prepend installed-package-only sys.path) and asserts no exception. Skip on missing alembic.ini-in-cwd scenario by setting `ATLAS20_DB_URL=sqlite://` (memory).

**Commit:** `fix(infra): ship audit — bundle alembic.ini + migrations + config in Docker runtime image`

---

### C2 — Docker compose missing worker service + README quickstart missing worker step

**Files:** `docker-compose.yml`, `README.md`.

**Problem (Codex):** README quickstart starts only `seed + API + frontend`. Compose has only `backend + web`. POST /api/backtests/run queues forever. Codex confirmed via E2E smoke: queued for 2s+, then ran `python -m atlas20.api.worker.main` and completion happened.

**Decision (Claude):** Add a `worker` service to docker-compose mirroring backend:

```yaml
services:
  backend:
    build: .
    # ... existing
  worker:
    build: .
    command: ["python", "-m", "atlas20.api.worker.main"]
    environment:
      # share same env as backend
      ATLAS20_ENV: dev
      ATLAS20_DB_URL: sqlite:///./data/atlas20.sqlite
      ATLAS20_REPORT_ROOT: /app/reports
      ATLAS20_DATA_ROOT: /app/data
      ATLAS20_PROJECT_ROOT: /app
      ATLAS20_DISABLE_SCHEDULER: "1"  # scheduler lives on the API process; worker shouldn't run it too
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports
    depends_on: [backend]  # ensure DB+migrations done before worker pulls
```

Update README quickstart "Run locally" section:
- Step 4: in a new terminal, `python -m atlas20.api.worker.main`
- Step 5 (docker compose): `docker compose up` now spawns 3 services; worker auto-starts

**Test:** docs only; manual verification.

**Commit:** `fix(infra): ship audit — add worker service to compose + document worker startup in README`

---

### C3 — Frontend missing X-API-Key header injection

**Files:** `apps/web/src/lib/api.ts`, new `apps/web/.env.example`.

**Problem (Opus arch):** `requestJson` helper at `api.ts:560-566` injects NO `X-API-Key` header. Backend `verify_api_key` returns "anonymous" only when `settings.api_keys` is empty. With keys configured in prod, every mutation route 401s silently — entire UI mutation surface broken.

**Decision (Claude):** Wire env-var-based API key injection:

```ts
// At top of api.ts:
const API_KEY = (import.meta.env.VITE_ATLAS20_API_KEY as string | undefined)?.trim();

// In requestJson helper:
const headers: Record<string, string> = {
  ...(init?.headers as Record<string, string> | undefined),
};
if (API_KEY) headers["X-API-Key"] = API_KEY;
// then pass headers into fetch
```

Create `apps/web/.env.example`:
```
# Optional: set when backend has ATLAS20_API_KEYS configured
VITE_ATLAS20_API_KEY=
```

Also need to handle the GET download URL builders (`downloadDigestUrl`, `downloadReportUrl`) — these use `window.open()` which can't send headers. For MVP per `docs/operations/security.md`, GET downloads are unauth — but verify the security doc is still aligned with this decision. (It already is per B14 — confirm in code.)

**Test:** add vitest case in `api.test.ts`:
- `import.meta.env.VITE_ATLAS20_API_KEY = "test-key"` (or vi.stubEnv)
- Mock fetch, call `runBacktest(...)`, assert fetch was called with `headers: { "X-API-Key": "test-key" }`
- Empty key → header NOT set

**Commit:** `fix(ui): ship audit — inject X-API-Key header from VITE_ATLAS20_API_KEY for mutation routes`

---

### C4 — `/api/universe/refresh` TS contract drift

**Files:** `apps/web/src/lib/api.ts`.

**Problem (Opus sec):** TS declares `requestJson<{refreshed_at: string}>(...)`, backend returns `{run_id, status}`. Mocks also wrong shape so tests don't catch.

**Decision:** Correct the TS type:

```ts
export function refreshUniverse() {
  return requestJson<{ run_id: string; status: string }>("/universe/refresh", { method: "POST" });
}
```

Update `apps/web/src/features/universe/UniverseHealthTab.test.tsx:29` mock to match real shape. If callers use `.refreshed_at` — replace with `.status === "queued" ? toast(...) : ...` or whatever makes semantic sense (currently none consume — just invalidate queries).

**Test:** existing test should pass after mock fix.

**Commit:** `fix(ui): ship audit — correct refreshUniverse TS type to {run_id, status} matching backend`

---

### C5 — `GenerateReportResponse` TS contract drift

**File:** `apps/web/src/lib/api.ts`.

**Problem (Opus sec + arch):** TS `{job_id, status, note?}` — backend returns `{job_id, status, files: ReportEntry[], warnings: string[]}`. Callers can't see warnings (e.g., "PDF skipped: weasyprint unavailable").

**Decision:**

```ts
export type GenerateReportResponse = {
  job_id: string;
  status: "completed";  // backend only ever returns this
  files: ReportEntry[];
  warnings: string[];
};
```

Surface warnings in `ReportsExportsTab` after `generateReport(...)` resolves — show toast with `response.warnings.join("; ")` when non-empty.

**Test:** add vitest case asserting toast renders warnings on partial-success response.

**Commit:** `fix(ui): ship audit — correct GenerateReportResponse TS shape and surface warnings to user`

---

### C6 — `GenerateReportRequest` TS missing `run_id` field

**File:** `apps/web/src/lib/api.ts`, `apps/web/src/features/reports/NewReportModal.tsx`.

**Problem (Opus arch):** Backend `schemas.py:GenerateReportRequest` accepts optional `run_id: RunId | None`. TS type omits it. UI can never target a specific run for re-generation.

**Decision:**

```ts
export type GenerateReportRequest = {
  // existing fields...
  run_id?: string;
};
```

Add a "Regenerate this run's report" CTA in `RunDetail` / `BacktestStudioTab` that POSTs with `{run_id: detail.run_id, formats: ["markdown", "pdf", "png", "bundle"]}`.

**Test:** add vitest case for the new CTA.

**Commit:** `feat(ui): ship audit — add run_id to GenerateReportRequest + Regenerate Report CTA in RunDetail`

---

### C7 — `record_report_generation` invalid format silently dropped in skipped path (Opus sec W upgraded to ship-quality issue)

Actually NOT a Critical — it's Warning. Demote. Will handle as W8 below.

---

## WARNING (W1-W11)

### W1 — Prod auth fail-open: empty `api_keys` allows anonymous mutations

**File:** `src/atlas20/api/settings.py`.

**Problem (Codex W elevated from Opus Info):** `enforce_prod_gates` checks CORS, secret_key, docs — but NOT non-empty `api_keys`. Combined with `verify_api_key` returning "anonymous" when empty → prod deployments without `ATLAS20_API_KEYS` allow open mutation access.

**Decision:** Add a prod-gate validator:

```python
if self.env == "prod" and not self.api_keys:
    raise ValueError("ATLAS20_API_KEYS must be set to a non-empty list in prod")
```

Add to `enforce_prod_gates` alongside the secret_key check.

**Test:** in `tests/test_settings.py`:
- prod + empty api_keys → ValidationError
- prod + non-empty api_keys → OK
- dev + empty api_keys → OK (existing dev workflow)

**Commit:** `fix(api): ship audit — require non-empty ATLAS20_API_KEYS in prod env`

---

### W2 — Docker HEALTHCHECK uses /healthz (no DB) instead of /readyz (DB+writes)

**File:** `Dockerfile`.

**Problem (Codex):** HEALTHCHECK hits `/healthz` which returns 200 unconditionally. Container appears "healthy" even when DB is down. Should use `/readyz`.

**Decision:** Change HEALTHCHECK to `/readyz`:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/readyz || exit 1
```

Bump `start-period` to 30s to give Alembic migrations time on first boot.

Also remove `/readyz` from access_log middleware exclusion list — codex flagged that `docs/operations/logging.md` says "alert on /readyz 503 via access log" but middleware excludes it. Either include `/readyz` in access logs (so alerts work) OR update logging.md to say "alert via /metrics histogram on /readyz duration" instead. Pick the simpler fix: include `/readyz` in access logs (no /readyz exclusion).

**File:** `src/atlas20/api/middleware/access_log.py` — drop `/readyz` from `excluded_paths`. Keep `/healthz` excluded (cheap probe, noisy).

**Test:** existing tests; verify access_log still excludes /healthz only.

**Commit:** `fix(infra): ship audit — Docker HEALTHCHECK uses /readyz; access log includes /readyz for SRE alerts`

---

### W3 — Worker lifecycle events not logged

**Files:** `src/atlas20/api/repositories/runs_repo.py`, `src/atlas20/api/worker/queue.py`, `worker/recovery.py`.

**Problem (Opus arch):** Run terminal transitions emit Prometheus counters but no structlog event. Incident triage has no breadcrumbs. Sentry contexts empty.

**Decision (Claude):** Add a `logger.info` in `_record_terminal_transition` (single chokepoint):

```python
def _record_terminal_transition(previous_status: str | None, run: Run | None) -> None:
    if run is None or run.status not in TERMINAL_BACKTEST_STATUSES:
        return
    if previous_status in TERMINAL_BACKTEST_STATUSES:
        return
    duration = _terminal_duration_seconds(run)
    record_backtest_terminal(run.status, duration)
    logger.info(
        "backtest.terminal",
        run_id=run.run_id,
        previous_status=previous_status,
        status=run.status,
        duration_s=duration,
        strategy=run.strategy,
    )
```

Also add a `logger.info("backtest.claimed", run_id=...)` in `queue.claim_one` before status change to "running".

Use `structlog.get_logger(__name__)` — already wired in `logging_config.py`.

**Test:** in `tests/test_metrics.py` or new `tests/test_worker_logs.py`:
- Trigger a terminal transition; capture logs via `caplog`; assert event=`"backtest.terminal"` and `run_id` present.

**Commit:** `fix(api): ship audit — emit structured logs on backtest lifecycle transitions`

---

### W4 — `/api/compare` route doesn't whitelist query params

**File:** `src/atlas20/api/routes/compare.py`.

**Problem (Opus arch):** `/runs` rejects unknown query params (B8); `/compare` doesn't. Typo `?ranges=YTD` silently defaults to `YTD` instead of 422.

**Decision:** Mirror the `/runs` whitelist pattern. Use FastAPI's request introspection at the top of `get_compare`:

```python
ALLOWED_COMPARE_QUERY = {"ids", "range"}

@router.get("/compare", response_model=ComparePayload)
def get_compare(
    request: Request,
    ids: list[str] = Query(default=[]),
    range: ChartRangeLiteral = Query(default="YTD"),
    session: Session = Depends(get_session),
) -> ComparePayload:
    unknown = set(request.query_params.keys()) - ALLOWED_COMPARE_QUERY
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown query parameter(s): {', '.join(sorted(unknown))}")
    return services.get_compare(session, ids, range)
```

**Test:** in `tests/test_compare.py` add `test_compare_rejects_unknown_query_params` asserting 422.

**Commit:** `fix(api): ship audit — reject unknown query params on /api/compare`

---

### W5 — `report_files.run_id` FK lacks cascade declaration

**Files:** `src/atlas20/api/db/models.py`, new migration.

**Problem (Opus arch):** FK has no `ondelete=...` clause. Future run-deletion (admin tool, backup cleanup) either orphans rows (SQLite) or blocks deletion (Postgres).

**Decision:** Declare `ondelete="SET NULL"` (artifacts survive run purge for audit; reports table allows `run_id` nullable already).

```python
class ReportFile(SQLModel, table=True):
    __tablename__ = "report_files"
    id: int | None = Field(default=None, primary_key=True)
    run_id: str | None = Field(
        default=None,
        sa_column=Column(String, ForeignKey("runs.run_id", ondelete="SET NULL"), nullable=True, index=True),
    )
    # ... rest unchanged
```

Add new alembic migration `20260521_0001_report_files_fk_set_null.py` that drops + recreates the constraint with ondelete.

**Test:** in `tests/test_runs_repo.py` add `test_deleting_run_sets_report_files_run_id_to_null` — insert run + report_file, delete run, assert report_file.run_id is None.

**Commit:** `fix(api): ship audit — report_files.run_id ON DELETE SET NULL + migration`

---

### W6 — `IdempotencyRepo.purge_expired` is O(N) load-then-delete

**File:** `src/atlas20/api/repositories/idempotency_repo.py`.

**Problem (Opus arch):** Loads all rows then deletes one-by-one. Called on every backtest POST. Pathological at scale.

**Decision:** Single bulk DELETE:

```python
from sqlalchemy import delete

def purge_expired(self) -> int:
    cutoff = _time.utc_now()
    stmt = delete(IdempotencyKey).where(IdempotencyKey.expires_at <= cutoff)
    result = self._s.exec(stmt)
    return result.rowcount or 0
```

**Test:** in `tests/test_idempotency_repo.py` (or wherever existing tests live) — verify bulk delete returns expected count + no rows remain.

**Commit:** `perf(api): ship audit — bulk DELETE for IdempotencyRepo.purge_expired`

---

### W7 — 3 services bypass repository layer

**Files:** `src/atlas20/api/services.py:585`, `services.py:612`, `routes/reports.py:103`.

**Problem (Opus arch):** Raw `session.exec(select(Run)...)` queries bypass `RunsRepo`. Breaks architectural invariant.

**Decision:** Add 2 repo methods:

```python
# in RunsRepo:
def find_latest_by_strategy_status(self, strategy: str, statuses: tuple[str, ...]) -> Run | None:
    stmt = (
        select(Run)
        .where(Run.strategy == strategy, Run.status.in_(statuses))
        .order_by(Run.created_at.desc(), Run.run_id.desc())
        .limit(1)
    )
    return self._s.exec(stmt).first()

def find_latest_completed_by_strategy(self, strategy: str | None) -> Run | None:
    stmt = select(Run).where(Run.status == "completed")
    if strategy:
        stmt = stmt.where(Run.strategy == strategy)
    return self._s.exec(stmt.order_by(Run.created_at.desc(), Run.run_id.desc()).limit(1)).first()
```

Replace the 3 raw queries with calls to these helpers.

**Test:** existing tests for `refresh_universe` and `_select_generate_run_id` should still pass — pure refactor.

**Commit:** `refactor(api): ship audit — route 3 raw session.exec callers through RunsRepo helpers`

---

### W8 — `record_report_generation` skipped path drops invalid formats (formats not in REPORT_FORMATS)

**File:** `src/atlas20/api/routes/reports.py:107-110`.

**Problem (Opus sec):** `_record_report_skipped` iterates `req.formats` and only emits the metric for formats in `REPORT_FORMATS`. Invalid formats are silently dropped. (Already partially aligned with C1 cardinality protection from the previous batch — verify this is intentional and document it.)

**Decision:** This IS intentional per round-2 W2 design (skip unknown formats from metric). Add a comment + INFO log so observability doesn't silently lose data:

```python
def _record_report_skipped(formats: list[ReportFormat]) -> None:
    for fmt in formats:
        if fmt in REPORT_FORMATS:
            record_report_generation(fmt, "skipped")
        else:
            logger.info("ignoring unknown format in skipped metric path: %s", fmt)
```

**Test:** existing tests; add caplog assertion if needed.

**Commit:** `docs(api): ship audit — log when _record_report_skipped drops unknown formats`

---

### W9 — `recover_my_own_stale_runs` effectively dead on real restart

**Files:** `src/atlas20/api/worker/recovery.py`, `worker/main.py`.

**Problem (Opus sec):** `recover_my_own_stale_runs` looks for `Run.worker_pid == os.getpid()` — but new PID never matches dead worker's PID. Function name is misleading.

**Decision (Claude):** Two options:
(a) Delete the function (relies on API lifespan's `recover_stale_runs` which uses heartbeat, not PID)
(b) Rename to clarify intent and document that it's a NO-OP unless PID reuse occurs

Pick (b) since deleting might break tests. Rename to `recover_runs_owned_by_pid(my_pid)` — clearly says "by PID match"; document why it matters (PID reuse on busy hosts, fork-and-restart in same process). Add a docstring explaining: "On a normal restart this returns 0 because the new PID differs from the dead worker's. Use `recover_stale_runs` (heartbeat-based) for the general restart case."

**Test:** existing tests should still pass — rename only.

**Commit:** `refactor(api): ship audit — rename recover_my_own_stale_runs to clarify PID-match semantics`

---

### W10 — `_publish_report_dir` backup-rename rollback unverified

**File:** `src/atlas20/reporting/report.py`.

**Problem (Opus sec):** Comment says "backup-rename semantics" but no test verifies that an OS-level failure between `.backup` rename and `tmp → final` rename actually rolls back the prior good version.

**Decision:** Add a regression test that simulates a mid-publish failure and verifies the prior `report_dir` is restored intact.

Use `monkeypatch.setattr` to make `shutil.move` raise after the first rename. Assert the original `report_dir` content is still present.

**File:** `tests/test_report_publish.py` (may already exist; if not, create).

**Commit:** `test(reporting): ship audit — verify _publish_report_dir rollback on mid-publish failure`

---

### W11 — `_sanitize_filename` strips Unicode

**File:** `src/atlas20/api/services_download.py:37-43`.

**Problem (Opus sec):** `SAFE_FILENAME_CHARS` keeps only ASCII alphanumerics + `._-`. Any non-ASCII filename → "report". Current filenames are all ASCII (digest.md etc.), so this is forward-looking only.

**Decision:** Allow Unicode letters via `\w` (which matches Unicode word chars in Python 3 regex by default):

```python
SAFE_FILENAME_CHARS = re.compile(r"[^\w.-]+", re.UNICODE)
```

Test: verify "atlas20_报告.md" sanitizes to "atlas20_报告.md" not "atlas20_.md".

**Commit:** `fix(api): ship audit — allow Unicode word chars in _sanitize_filename`

---

## INFO (I1-I3)

### I1 — `.env.example` missing 7 settable fields

**File:** `.env.example`.

**Problem (Opus arch):** Missing `cors_allow_credentials`, `backup_root`, `backup_retention_days`, `run_timeout_seconds`, `worker_poll_interval_seconds`, `worker_heartbeat_interval_seconds`, `worker_cancel_grace_seconds`.

**Decision:** Add all 7 with comments + default values shown.

**Commit:** `docs(infra): ship audit — extend .env.example with worker + backup + CORS-creds settings`

---

### I2 — CI missing security scans

**File:** `.github/workflows/ci.yml`.

**Problem (Opus arch):** No `pip-audit`, `npm audit`, CodeQL, Trivy, SBOM, dependabot.

**Decision (Claude):** Add a `security-scan` job to ci.yml that runs `pip-audit` + `npm audit --audit-level=moderate`. CodeQL/Trivy/SBOM deferred (need GitHub setup beyond a CI yaml change).

```yaml
  security-scan:
    name: Dependency security scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - run: python -m pip install pip-audit
      - run: pip-audit --strict
      - uses: actions/setup-node@v5
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - run: npm --prefix apps/web ci --ignore-scripts
      - run: npm --prefix apps/web audit --audit-level=moderate
```

`pip-audit --strict` may flag transitive issues; if false-positives, allow with `--ignore-vuln <id>` documented in commit body.

**Commit:** `fix(ci): ship audit — add pip-audit + npm audit security-scan job`

---

### I3 — Frontend axe.test.tsx renders tabs in isolation, not full page (Opus sec follow-up)

**File:** `apps/web/src/test/axe.test.tsx`.

**Problem (Opus sec I-2 implicit):** Per-tab axe tests don't catch issues that emerge at the page level (e.g., the nested-main bug B15 had).

**Decision:** Already partially addressed (B15 W3 added the composed axe case). Audit: confirm every important page composition has at least one composed axe test. Add if missing.

If already covered (composed test exists per B15 round-2), this is a NO-OP info — skip and mark in commit log.

**Commit:** `test(ui): ship audit — confirm axe.test.tsx page-composition coverage` (or SKIP if already covered)

---

## Procedure

21 atomic commits. Order matters for some:
1. C1 (Dockerfile alembic/migrations/config) — foundation for C2
2. C2 (compose worker + README)
3. C3 (frontend X-API-Key)
4. C4 (refreshUniverse TS)
5. C5 (GenerateReportResponse TS)
6. C6 (GenerateReportRequest TS + Regenerate CTA)
7. W1 (prod api_keys gate)
8. W2 (HEALTHCHECK + access_log readyz)
9. W3 (worker lifecycle logs)
10. W4 (/compare whitelist)
11. W5 (FK cascade migration)
12. W6 (purge_expired bulk DELETE)
13. W7 (services bypass repos refactor)
14. W8 (skipped format log)
15. W9 (recovery rename)
16. W10 (publish rollback test)
17. W11 (Unicode filename)
18. I1 (.env.example expand)
19. I2 (CI security scan)
20. I3 (axe composition audit — may be NO-OP commit)

After each: `python -m pytest tests/ -x -q` green; frontend `npm test` green if UI touched.

**Final acceptance:**
- pytest 332 → ~342 (W3, W4, W5, W10, plus W1/C7 add)
- vitest 157 → ~160 (C3, C5, C6 add)
- typecheck/lint clean
- `python scripts/verify_release.py` exit 0
- `git diff --check 3bfb2df..HEAD` clean
- Manual: if docker available, `docker build .` succeeds
- Manual: review the alembic.ini script_location compatibility (works from repo root AND in container)

## Report

- ~20 commit hashes (skip count may vary)
- Final backend test count
- Final frontend test count
- verify_release.py exit
- Any Dockerfile/docker-compose verification status
- Any deviations (Claude triages)
</TASK>
