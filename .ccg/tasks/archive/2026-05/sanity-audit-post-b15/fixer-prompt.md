ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Atlas20 full-repo sanity-audit findings. Combined Claude + codex
post-B15 audit. 6 atomic fixes (1 Critical / 4 Warning / 1 Info per user
"info 也都改完"). **Each = separate commit.**

Range: starts from current HEAD `d73ce8f`.

After all 6 land: `python scripts/verify_release.py` must exit 0.

---

## C1 (Critical) — Release gate failures

**Files:** `scripts/check_repo_health.py`, `.ccg/tasks/archive/2026-05/batch-14-phase-o/round-1-fixer.md`, `.ccg/tasks/archive/2026-05/batch-7-persistence/round-2-fixer.md`, possibly others flagged by `git diff --check`.

**Problem (Codex audit):** Two-part release gate is broken:
1. `git diff --check d73ce8f~30..HEAD` reports trailing whitespace in archived `.ccg/tasks/archive/*.md` files (CCG task records, not code) — typically harmless but blocks `verify_release.py`.
2. `scripts/check_repo_health.py` scans archived/test strings as credential assignments and flags `tests/test_settings.py` (which contains intentional test dummy secrets) + likely the archive `.md` files referencing `secret_key = "dev-only-..."`.

**Decision (Claude):** Two-part fix in ONE commit (they're inseparable
release-gate logic):

1. Strip trailing whitespace from the offending archive `.md` files:
   - `.ccg/tasks/archive/2026-05/batch-14-phase-o/round-1-fixer.md` line 5
   - `.ccg/tasks/archive/2026-05/batch-7-persistence/round-2-fixer.md` lines 54, 56
   - Sweep ALL archived `.md` files for trailing whitespace as a one-shot
     `sed -i 's/[ \t]*$//'` (the CCG task records are append-only history,
     stripping cosmetic whitespace is safe).

2. In `scripts/check_repo_health.py`, exclude `.ccg/tasks/archive/**` from
   the credential-pattern scan AND whitelist `tests/**` for the specific
   "secret_key = " false-positive pattern (intentional test dummies, not
   real secrets).

   Quick approach: read the script (it's ~50 lines per Codex), add an
   exclusion list at the top:

   ```python
   EXCLUDE_PATHS = (
       ".ccg/tasks/archive/",  # historical task records, intentional secret examples
       "tests/",                # intentional test dummy secrets
   )
   ```

   And in the scanning loop, skip any path starting with one of these
   prefixes.

3. **Verify** `python scripts/verify_release.py` exits 0 after both changes.

**Test:** `python scripts/verify_release.py` returns 0 (or skips with
documented reason if other gates fail unrelatedly — investigate them too).

**Commit:** `fix(infra): sanity audit — repo-health scan excludes archive + tests; strip trailing whitespace in archived task notes`

---

## W1 (Warning) — Missing rate limit on POST /runs/{id}/favorite

**File:** `src/atlas20/api/routes/runs.py:69-74`.

**Problem (Codex):** `POST /api/runs/{run_id}/favorite` has `verify_api_key`
dependency but no SlowAPI limit decorator. Adjacent `POST /runs/{id}/cancel`
already has `@limiter.limit("30/minute")`. Cancel and favorite are both
state-mutating user-controlled endpoints; both deserve a limit.

**Decision (Claude):** Add `@limiter.limit("60/minute")` (favorite is a more
common action than cancel, so allow 2× cancel's limit). Update the function
signature to accept `Request` + `Response` per SlowAPI's `headers_enabled=True`
pattern (matches cancel route shape from B11).

```python
@router.post("/runs/{run_id}/favorite", dependencies=[Depends(verify_api_key)])
@limiter.limit("60/minute")
def post_run_favorite(
    request: Request,
    response: Response,
    run_id: RunId,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    del request, response
    result = services.toggle_run_favorite(session, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="run not found")
    return result
```

**Test:** in `tests/test_rate_limit.py` add `test_favorite_route_rate_limited`
mirroring the existing `test_cancel_route_rate_limited` pattern: hit 60 ×
202, then assert next call returns 429 with Retry-After header.

**Commit:** `fix(api): sanity audit — rate-limit POST /runs/{id}/favorite at 60/min`

---

## W2 (Warning) — Report generation metric not emitted on no-completed-run path

**File:** `src/atlas20/api/routes/reports.py:55-62`.

**Problem (Codex):** `generate_report` route returns
`{"status": "completed", "files": []}` when no completed run is available,
WITHOUT calling `record_report_generation(...)`. Same for the
HTTPException-handler branch at line 65-75 that swallows legacy errors.
Metric undercounts the "no-op skip" path.

**Decision (Claude):** When the no-run path is taken (lines 55-62), emit
`record_report_generation(fmt, "skipped")` for each requested format. This
adds a third status label value alongside `completed` / `failed`. Update
the docstring on `record_report_generation` to document the 3 statuses.

```python
if run_id is None:
    for fmt in req.formats:
        if fmt in REPORT_FORMATS:
            record_report_generation(fmt, "skipped")
    return {
        "job_id": "report-none",
        "status": "completed",  # HTTP-level success; report-level "skipped"
        "files": [],
        "warnings": ["no completed run available for report generation"],
    }
```

Do NOT change the response shape (keep `status: "completed"`) — that's the
HTTP-level contract. The metric records the report-generation business
status.

**Test:** in `tests/test_metrics.py` add case:
- POST /reports/generate when DB has no completed runs → response 202 +
  body status="completed" + `atlas20_report_generations_total{format="markdown",status="skipped"}` incremented.

**Commit:** `fix(api): sanity audit — emit report_generations_total{status="skipped"} on no-completed-run path`

---

## W3 (Warning) — Nested `<main>` landmark violation

**Files:** `apps/web/src/components/layout/AppShell.tsx:30`,
`apps/web/src/pages/ResearchConsolePage.tsx:65`.

**Problem (Codex):** AppShell wraps children in `<main>{props.children}</main>`,
AND ResearchConsolePage adds its own `<main id="main-content">` (added in
B15 W2 to make the skip-link target a landmark). Two nested `<main>`
elements violate WCAG (`landmark-no-duplicate-main`). axe might not catch
this in the per-tab test because the test renders ResearchConsolePage in
isolation, not through AppShell.

**Decision (Claude):** AppShell is structural shell (header/sidebar layout);
it should NOT own the `<main>` landmark. Pages own their semantic main.
Change AppShell to `<div>{props.children}</div>` (or a more semantic wrapper
if AppShell has shell semantics — but `<main>` is specifically for the
page's primary content).

Adjust: in `AppShell.tsx:30`, change `<main>` to `<div className="app-shell-main">`.
Add a corresponding CSS rule in `index.css` if AppShell had styling tied to
the `main` tag (verify — likely none since AppShell uses inline styles).

Keep `ResearchConsolePage.tsx:65` `<main id="main-content">` unchanged
(skip-link target + the canonical landmark).

**Test:** add an axe test that renders ResearchConsolePage INSIDE AppShell to
catch this regression class going forward. Place in
`apps/web/src/test/axe.test.tsx`.

**Commit:** `fix(ui): sanity audit — remove nested <main> in AppShell, keep ResearchConsolePage landmark`

---

## W4 (Warning) — Makefile typecheck broader than CI

**File:** `Makefile`.

**Problem (Codex):** `make typecheck` runs `mypy --strict src/atlas20/api`
which fails with ~145 errors today (whole API surface). CI only enforces
strict on 3 leaf files (`schemas.py settings.py _metrics.py` per
`.github/workflows/ci.yml:64`). Developer running `make typecheck` locally
sees 145 errors and assumes the repo is broken; the CI gate is actually
narrower. Misleading.

**Decision (Claude):** Align Makefile with CI. Two-line change in
`Makefile`:

```makefile
typecheck:
	mypy --strict src/atlas20/api/schemas.py src/atlas20/api/settings.py src/atlas20/api/_metrics.py
	npm --prefix apps/web run typecheck
```

Document above the target:
```makefile
# typecheck mirrors CI's mypy strict-pilot scope (schemas, settings, _metrics).
# Expand the file list here AND in .github/workflows/ci.yml when the strict
# pilot grows.
```

**Test:** `make typecheck` exits 0.

**Commit:** `fix(infra): sanity audit — align Makefile typecheck with CI strict-pilot scope`

---

## W5 (Info → upgrade to Warning by Claude) — React act() warnings in axe tests

**File:** `apps/web/src/test/axe.test.tsx`.

**Problem (Codex):** Axe-tab coverage tests trigger React 18 `act(...)`
warnings on BacktestStudioTab, RunHistoryTab, ReportsExportsTab (per dispatcher
B15 stderr output). Tests pass but warnings indicate state updates outside `act`,
which can mask real issues.

**Decision (Claude):** Wrap each axe assertion in `await waitFor(...)` or
mark the test as `async` and `await new Promise(...)` to flush microtasks
before running axe:

```tsx
it("BacktestStudioTab has no axe violations", async () => {
  const { container } = renderWithQuery(<BacktestStudioTab />);
  // Let any pending useEffect / useQuery effects settle before axe
  await waitFor(() => expect(container.querySelector("[data-testid]")).toBeInTheDocument());
  expect(await axe(container, axeOptions)).toHaveNoViolations();
});
```

Or simpler: `await new Promise(resolve => setTimeout(resolve, 0))` to flush
the microtask queue before axe.

Iterate over the 6 tab tests; some may already be act-clean (Overview /
Universe / Compare). Only patch the ones emitting warnings.

**Test:** `npm run test -- --run` shows zero `act(...)` warnings in stderr
(or document remaining ones as known with rationale).

**Commit:** `test(ui): sanity audit — flush React effects before axe assertions to silence act warnings`

---

## I1 (Info, defer or quick) — `time.sleep(1.1)` in test_generate_report.py

**File:** `tests/test_generate_report.py:179`.

**Problem (Codex):** One backend test uses `time.sleep(1.1)` to verify PNG
regeneration produces a newer mtime. 1.1 seconds of slow CI per run.

**Decision (Claude):** Replace with `time.time_ns()` comparison OR set the
PNG mtime explicitly before regen via `os.utime(png_path, (past_t, past_t))`
then assert post-regen mtime > past_t. Fully synchronous, no sleep.

```python
import os, time
# replace time.sleep(1.1) with:
past_t = time.time() - 5
os.utime(png_path, (past_t, past_t))
# ...regenerate...
assert png.stat().st_mtime > past_t  # any future mtime works
```

**Test:** existing PNG regeneration assertion still passes; total runtime
drops by ~1s.

**Commit:** `test(api): sanity audit — replace time.sleep(1.1) with os.utime in PNG regen test`

---

## Procedure

6 atomic commits in order: C1 → W1 → W2 → W3 → W4 → W5 → I1.

(That's 7 commits — I1 included since user "info 也都改完".)

After each: `python -m pytest tests/ -x -q` green (327 expected; W1 adds 1,
W2 adds 1, W5 doesn't add, I1 modifies — final ~329).

Frontend test count: W3 may add 1 (AppShell+ResearchConsolePage axe case);
final ~157.

Final acceptance:
- `python scripts/verify_release.py` exits 0
- `make typecheck` exits 0
- backend pytest ~329 passing
- frontend vitest ~157 passing
- typecheck / lint / build clean

## Report

- 7 commit hashes
- Final backend test count
- Final frontend test count
- `verify_release.py` exit code
- Any deviations (Claude triages)
</TASK>
