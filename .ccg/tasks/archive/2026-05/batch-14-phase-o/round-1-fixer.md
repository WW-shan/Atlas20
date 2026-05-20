ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 14 Round-1 reviewer findings. Combined Opus 4.7 (86/100) + codex
(77/100) review on commit `4d075be feat(api): R14 batch 14 — phase O
observability`. 

11 atomic fixes (2 Critical, 5 Warning, 4 Info per user directive "info 也都改完").
**Each = separate commit.** Run pytest after each. Frontend test count stays
132; backend climbs 316 → ~321.

Range starts from current HEAD `4d075be`.

---

## C1 (Critical) — services_report metric cardinality DoS + unguarded counter

**File:** `src/atlas20/api/services_report.py` (around lines 244-297).

**Problem (Opus-I1 + Codex-Critical-part):** The format-validation `raise
HTTPException(422)` lives INSIDE the `try:` block. When an attacker POSTs with
a custom format like `__atk_<random>__`, the except block iterates `requested`
(raw caller input) and emits `atlas20_report_generations_total{format=<UNBOUNDED>}`
labels. Plus: `record_report_generation()` call has no try/except guard, so a
prometheus_client failure crashes report generation.

**Decision (Claude):** Two-part fix.

1. **Move validation OUT of `try:`** so 422 never reaches the metric path:
   ```python
   requested = {str(item) for item in formats}
   unknown = requested - REPORT_FORMATS
   if unknown:
       raise HTTPException(status_code=422, detail=f"unsupported report format: {sorted(unknown)[0]}")
   if not requested:
       raise HTTPException(status_code=422, detail="formats must not be empty")
   try:
       # ... rest of generation flow stays inside try
   except Exception:
       for format_name in requested & REPORT_FORMATS:  # belt-and-braces clamp
           _safe_record_report_generation(format_name, "failed")
       raise
   ```

2. **Wrap the counter call in a small helper** that swallows any prometheus
   error and logs at WARN level:
   ```python
   def _safe_record_report_generation(format_name: str, status: str) -> None:
       try:
           record_report_generation(format_name, status)
       except Exception:
           logger.warning("failed to record report generation metric", exc_info=True)
   ```
   Use it everywhere `record_report_generation` was called previously.

**Test:** in `tests/test_metrics.py`:
- POST `/api/reports/generate` with `formats=["__not_a_format__"]` → 422 AND
  `atlas20_report_generations_total` should NOT contain `format="__not_a_format__"`
  label.
- Monkeypatch `record_report_generation` to raise; assert generation flow still
  succeeds with logged warning.

**Commit:** `fix(api): batch 14 reviewer pass — clamp report metric labels to known formats and guard counter calls`

---

## C2 (Critical) — Rate-limit counter cardinality + unguarded call

**File:** `src/atlas20/api/dependencies/ratelimit.py` (around lines 29-31).

**Problem (Opus-I2 + Codex-Critical-part):** Falls back to
`request.url.path` (contains concrete IDs like `/runs/btk_0142`) when the
templated route isn't in scope. Plus: no try/except around the counter call.
Pre-warming missing for `route="unmatched"` (Opus-N6 Info bundled here).

**Decision:** Drop the raw-path fallback entirely; emit nothing if route is
None. Wrap in try/except. Pre-warm `route="unmatched"` so dashboards see the
series at startup.

```python
def _safe_record_rate_limit_hit(route_path: str) -> None:
    try:
        record_rate_limit_hit(route_path)
    except Exception:
        logger.warning("failed to record rate limit metric", exc_info=True)

# In the 429 handler:
route = request.scope.get("route")
route_path = getattr(route, "path", None)
if route_path:
    _safe_record_rate_limit_hit(route_path)
# else: don't increment; unknown route means 404/SlowAPI internal — out of scope
```

**Test:** in `tests/test_metrics.py`:
- Trigger 429 on a templated route (e.g. POST /backtests/run repeated) →
  counter contains `route="/backtests/run"` NOT `route="/backtests/run/<id>"`.
- Monkeypatch `record_rate_limit_hit` to raise → 429 response still returned.
- Initial metrics scrape (before any 429) contains `route="unmatched"` label
  with value 0 (pre-warmed).

**Commit:** `fix(api): batch 14 reviewer pass — drop raw-path rate-limit metric fallback and guard counter calls`

---

## W1 (Warning) — runs_repo metric calls not guarded

**File:** `src/atlas20/api/repositories/runs_repo.py` around line 33 (the
`_record_terminal_transition` body) and `_metrics.py:40` if `record_backtest_terminal`
is the call site.

**Problem (Codex-Critical-runs_repo subset):** Same as C1/C2 — bare
`record_backtest_terminal(...)` invocation. A prometheus error here would
break the run-status update flow (catastrophic).

**Decision:** Move the try/except into `record_backtest_terminal` itself (in
`_metrics.py`) so ALL future callers are safe by default, OR wrap at the
call site. Prefer the former — single guard point.

```python
# in _metrics.py
def record_backtest_terminal(status: str, duration_seconds: float | None) -> None:
    try:
        BACKTESTS_TOTAL.labels(status=status).inc()
        if duration_seconds is not None:
            BACKTEST_DURATION_SECONDS.observe(duration_seconds)
    except Exception:
        logger.warning("failed to record backtest terminal metric", exc_info=True)
```

(Add `logger = logging.getLogger(__name__)` at module top of `_metrics.py` if
not present.)

Mirror the pattern for `record_report_generation` and `record_rate_limit_hit`
in `_metrics.py` so C1/C2's wrapper helpers can call the simple `record_*`
form. Actually — cleaner: put the try/except INSIDE the `_metrics.py` recorder
functions, so C1's `_safe_record_report_generation` and C2's
`_safe_record_rate_limit_hit` become unnecessary. Pick one pattern; bake it
all into `_metrics.py`.

**Test:** `tests/test_metrics.py`:
- Monkeypatch the underlying Counter `.inc()` to raise → `record_backtest_terminal`
  doesn't raise; logged warning visible via caplog.

**Commit:** `fix(api): batch 14 reviewer pass — centralize metric error handling in _metrics recorders`

(If you make this commit before C1/C2, you can simplify those by removing the
wrapper helpers. Do this one FIRST, then C1/C2 above use the centralized
guards.)

**ORDER ADJUSTMENT:** Apply W1 FIRST, then C1, then C2.

---

## W2 (Warning) — Missed terminal transitions in queue.py + recovery.py

**Files:** `src/atlas20/api/worker/queue.py:27`,
`src/atlas20/api/worker/recovery.py:27,42`.

**Problem (Codex):** Three additional terminal-transition sites bypass
`RunsRepo._record_terminal_transition`:
- `queue.py:27` — pre-spawn cancel (status → "cancelled")
- `recovery.py:27` — startup stale recovery (status → "failed")
- `recovery.py:42` — worker restart recovery (status → "failed")

None call `record_backtest_terminal`, so dashboards undercount cancellations
and worker-death failures.

**Decision:** Add `record_backtest_terminal(<status>, <duration>)` at each
site, immediately after the `run.status = ...` assignment. Use
`runs_repo._terminal_duration_seconds(run)` if accessible (export from
runs_repo as a public helper) OR inline the same logic.

After the fix, the 3 sites should look like:

```python
# queue.py:27
candidate.status = "cancelled"
candidate.error = "cancelled before execution"
record_backtest_terminal("cancelled", terminal_duration_seconds(candidate))

# recovery.py:27, :42
run.status = "failed"
run.error = STALE_HEARTBEAT_ERROR
record_backtest_terminal("failed", terminal_duration_seconds(run))
```

Export `terminal_duration_seconds` from runs_repo (rename `_terminal_duration_seconds`
to drop the leading underscore, or add a public alias) so worker/* can import
without dunder access.

**Test:** in `tests/test_metrics.py`:
- Trigger queue cancel → `atlas20_backtests_total{status="cancelled"}` += 1
- Trigger recovery (stale heartbeat) → `atlas20_backtests_total{status="failed"}` += 1

**Commit:** `fix(api): batch 14 reviewer pass — emit backtests_total on queue cancel + worker recovery paths`

---

## W3 (Warning) — Duration histogram source semantics

**File:** `src/atlas20/api/repositories/runs_repo.py:_terminal_duration_seconds`.

**Problem (Codex):** Brief specified "observe `(finished_at - started_at).total_seconds()`"
but current code uses `run.duration_s` (set externally) or
`utc_now() - run.started_at` (a "now" approximation).

**Decision:** Schema currently has `duration_s` (worker writes it) but no
explicit `finished_at`. Adding `finished_at` is a schema change beyond Phase O
scope. Acceptable middle ground:
- When `duration_s` is set → use it (worker's measurement is authoritative).
- Else when `started_at` is set AND status is terminal → use `utc_now()` as
  proxy for finished_at, with a comment explaining this is an upper-bound
  estimate (off by the time between actual finish and DB commit, usually <
  1s).
- Else → return None and DON'T observe (better no data than misleading data).

Add a comment block explaining the semantics. No code change really needed
if the current logic already matches this (it does — verify and just add the
explanatory comment). If `duration_s` is missing AND `started_at` is None,
ensure we return None (do NOT observe 0).

**Test:** `tests/test_metrics.py`:
- Run with `duration_s=42.5` → histogram observes 42.5
- Run with `started_at` 10s ago, no `duration_s` → histogram observes ~10
- Run with neither → histogram NOT observed (no zero entries)

**Commit:** `docs(api): batch 14 reviewer pass — document duration histogram semantics; reject observe when duration unknown`

---

## W4 (Warning) — Sentry test global state isolation

**Files:** `tests/test_sentry.py`, `tests/conftest.py`.

**Problem (Opus-W1):** Tests monkeypatch `sentry_sdk.init` per-test but never
reset the process-global `sentry_sdk.Hub`. Future tests using real Sentry init
would leak.

**Decision:** Add an autouse fixture in `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _isolate_sentry_hub():
    """Reset Sentry global state before and after each test."""
    import sentry_sdk
    sentry_sdk.Hub.current.bind_client(None)
    yield
    sentry_sdk.Hub.current.bind_client(None)
```

Document at the top of `tests/test_sentry.py` why each test must use
`monkeypatch.setattr(sentry_sdk, "init", ...)` — protects against accidental
real-network calls.

**Test:** no new test; the autouse fixture covers all future cases.

**Commit:** `test(api): batch 14 reviewer pass — isolate sentry_sdk global hub per test via autouse fixture`

---

## W5 (Warning) — Duplicate redact_sensitive in JSON pipeline

**File:** `src/atlas20/api/logging_config.py:29-48`.

**Problem (Opus-W2):** `redact_sensitive` is registered both in
`shared_processors` AND in the `ProcessorFormatter.processors=[...]` list →
every log line walks the dict twice. Idempotent so output is correct, but
wasteful.

**Decision:** Drop `redact_sensitive` from the inner `processors=[...]` list
(line 45). Keep only the entry in `shared_processors` / `foreign_pre_chain`.

**Test:** existing `tests/test_log_redact.py` still passes (verify).

**Commit:** `perf(api): batch 14 reviewer pass — drop duplicate redact_sensitive from ProcessorFormatter chain`

---

## Info items (per user directive "info 也都改完")

### I1 — Anchor excluded_handlers regex

**File:** `src/atlas20/api/middleware/metrics.py:15`.

**Problem (Opus-N1):** `excluded_handlers=["/healthz", "/readyz"]` are regex,
unanchored → would match e.g. `/api/v1/healthz/probe` if such routes existed.

**Decision:** Anchor: `["^/healthz$", "^/readyz$"]`. Verify the
prometheus-fastapi-instrumentator docs use anchored patterns elsewhere.

**Commit:** `fix(api): batch 14 reviewer pass — anchor instrumentator excluded_handlers regex`

### I2 — Pre-warm RATE_LIMIT_HITS_TOTAL "unmatched" label

ALREADY BUNDLED INTO C2 above. SKIP separate commit.

### I3 — /readyz instrumentation decision in docs

**File:** `docs/operations/logging.md`.

**Problem (Opus-W3):** Brief left "/readyz: include in metrics?" open.
Code excluded it. Document the choice.

**Decision:** Add a short paragraph to `docs/operations/logging.md` explaining:
"`/readyz` is excluded from Prometheus instrumentation because the probe is
too short-lived (< 5ms typical) for histogram bucket distribution to be
meaningful. Alert on 503 rate via the access log instead (`status_code >= 500
AND path == "/readyz"`)."

**Commit:** `docs(ops): batch 14 reviewer pass — document /readyz exclusion from Prometheus instrumentation`

### I4 — Cross-reference new endpoints in security.md

**File:** `docs/operations/security.md`.

**Problem (Opus-N3):** Existing security doc enumerates auth posture for API
routes but doesn't mention the three new unauth endpoints.

**Decision:** Append a "MVP unauthenticated endpoints" section listing
`/healthz`, `/readyz`, `/metrics` with the gate rationale (bind localhost or
reverse-proxy allow-list in prod).

**Commit:** `docs(ops): batch 14 reviewer pass — cross-reference /healthz /readyz /metrics in security.md`

---

## Info items intentionally NOT fixed (rationale)

- **Opus-N2** scheduler shutdown wrapper pattern — current code is correct; the alternative (subclass override) is stylistic. Not blocking.
- **Opus-N4** squashed commit — informational only, refers to BUILDER pass; fixer pass below uses separate commits per finding. No action.
- **Opus-N5** lock-shutdown idempotency edge — current code is correct (verified by Opus). No action.

---

## Procedure

11 atomic commits in order:
1. **W1** (centralize metric guards — foundation for C1/C2)
2. **C1** (services_report cardinality + uses W1 centralized guard)
3. **C2** (ratelimit fallback drop + pre-warm — uses W1 guard)
4. **W2** (queue + recovery terminal transitions)
5. **W3** (duration semantics — docs/comments + None when unknown)
6. **W4** (Sentry autouse isolation)
7. **W5** (drop redact double-pass)
8. **I1** (anchor regex)
9. **I3** (docs/operations/logging.md /readyz exclusion note)
10. **I4** (docs/operations/security.md endpoints cross-ref)

(I2 is bundled into C2; that's 10 commits, not 11 — verify.)

After each: `python -m pytest tests/ -x -q` green. Frontend untouched (132).

Expect final pytest: 316 + ~5 new tests = **~321 passing**, 2 skipped unchanged.

## Report

- 10 commit hashes (or note if I2 was kept separate)
- Final backend test count
- Frontend test count (must be 132)
- Any deviations (Claude triages)
</TASK>
