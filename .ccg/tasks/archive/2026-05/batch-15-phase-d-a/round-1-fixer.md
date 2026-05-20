ROLE_FILE: C:\Users\WW\.claude\.ccg\prompts\codex\builder.md
<TASK>
Apply Batch 15 Round-1 reviewer findings. Combined Opus 4.7 (62/100) + codex
(60/100) review on 5 builder commits. Note: archive commit `1059351` was
already REVERTED in `72e04ce` (premature per protocol; archive will be re-done
after round-2 completes).

10 atomic fixes (5 Critical + 5 Warning). **Each = separate commit.** Run
pytest + npm test after each. Frontend test count climbs 150 → ~155; backend
stays 327.

Range: starts from current HEAD `72e04ce`.

---

## C1 (Critical) — W2: `.mono` wrap on remaining HTML numeric sites

**Files (codex-identified):**
- `apps/web/src/components/history/RunTable.tsx:180`
- `apps/web/src/features/history/RunHistoryTab.tsx:253`
- `apps/web/src/components/compare/ComparisonTable.tsx:131`
- `apps/web/src/components/compare/JaccardHeatmap.tsx:113`
- ALSO audit: `apps/web/src/components/backtest/EquityWorkspace.tsx:13,83,84,86`
  (these may already be inside `KpiTile` that has `.mono` — verify)

**Problem (Opus/Codex confirmed):** Some HTML-rendered numerics/timestamps are
not wrapped in `<span className="mono">` or rendered via a `.mono` ancestor.
Per Batch 12 R3 review W2, the gap is in HTML-side (SVG side was already
fixed in Batch 12).

**Decision (Claude):** For each cited line:
1. Read the line context
2. If the value is already inside a `className="mono"` ancestor or component
   (KpiTile, HeroKpi, RunTable td that has `.mono` from parent), SKIP — note
   in commit message
3. Otherwise wrap the numeric value: `<span className="mono">{value}</span>`
4. Make minimal edits — preserve existing structure

If the 4 codex-cited lines turn out to already be `.mono`-correct after
inspection (Opus said most were already wrapped), then the commit message
should note "after re-audit at HEAD, 0 unwrapped sites confirmed; commit is
no-op". In that case still produce the commit (touching the brief or a
NOTES.md to record the audit conclusion).

**Test:** existing tests still pass; no new test required.

**Commit:** `fix(ui): batch 15 reviewer pass — W2 audit HTML numeric mono wrapping`

---

## C2 (Critical) — W8: Delete stale CSS selectors

**File:** `apps/web/src/styles/index.css`.

**Problem (Opus-identified orphan list, verified by grep):**

| Lines | Selector | Status |
|---|---|---|
| 334-356 | `.topbar`, `.topbar h1`, `.topbar p`, `.hero-summary p` | orphan |
| 358-373 | `.sparkline`, `.sparkline rect`, `.sparkline path` | orphan (sparkline is data prop, not class) |
| 375-390 | `.logic-grid`, `.logic-grid div`, `.logic-grid span`, `.status-list span` | orphan |
| 392-394 | `.table-wrap` | orphan |
| 420-449 | `.dashboard-grid`, `.sidebar`, `.run-rail`, `.sidebar__header` | orphan |
| 469-488 | `.workspace`, `.status-list`, `.status-list div`, `.status-list strong` | orphan |
| 490-505, 569, 577 | `.hero-summary`, `.overview-grid`, `.metric-grid`, `.run-rail`, `.tab-switcher` (inside @media) | orphan |
| 102-106 | `.text-*` utilities | orphan (Codex flagged) |
| 262, 273 | `.topnav-tab--active` | KEEP — Opus noted "champion/featured semantic", borderline OK |

**Decision (Claude):** Delete all orphan rules per Opus's list. KEEP
`.topnav-tab--active` (line 262, 273) for now — it's gold for active tab and
borderline semantic; don't accidentally regress visual.

**Audit each delete:** For each selector, before removing run `grep -rn
'className="[^"]*\bSELECTOR\b' apps/web/src/` — if 0 hits, delete. If any
hit, KEEP and note in commit message.

Approx ~150 lines deletable.

**Test:** `cd apps/web && npm run test -- --run && npm run build` — both pass
after cleanup (build pass = no live CSS reference to deleted selectors).

**Commit:** `refactor(ui): batch 15 reviewer pass — W8 stale CSS cleanup`

---

## C3 (Critical) — Dockerfile editable-install runtime path mismatch

**File:** `Dockerfile`.

**Problem (both reviewers):** Builder runs `pip install --user -e ".[dev]"`
in `WORKDIR /build`. The editable `.pth` records `/build/src`. Runtime stage
copies `/root/.local → /home/atlas/.local` but source moves to `/app/src` →
`ModuleNotFoundError: No module named 'atlas20'` at uvicorn startup.

Secondary: `[dev]` installs pytest/ruff/mypy into production image.

**Decision (Claude):** Drop `-e` and `[dev]`:

```dockerfile
# Build stage
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev \
    libpango-1.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --user .

# Runtime stage
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 atlas
USER atlas
WORKDIR /app
COPY --from=builder --chown=atlas:atlas /root/.local /home/atlas/.local
COPY --chown=atlas:atlas docs ./docs
ENV PATH=/home/atlas/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1
CMD ["uvicorn", "atlas20.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

Key changes:
- Builder: `pip install . ` (no `-e`, no `[dev]`) — source installed into
  site-packages, not editable
- Runtime: drop the `COPY src ./src` line — package is in `/home/atlas/.local/...`
- Add `curl` to runtime apt deps (needed by HEALTHCHECK)
- Drop `pyproject.toml` copy in runtime (no longer needed)

**Test:** if `docker` CLI available, run `docker build -t atlas20-backend:test .`
to verify image builds. If not available, document as ops-attention "not
locally verified; CI must build" in the commit body.

**Commit:** `fix(infra): batch 15 reviewer pass — Dockerfile non-editable install + drop dev deps from runtime`

---

## C4 (Critical) — axe-core undeclared in package.json

**Files:** `apps/web/src/test/setup.ts:3`, `apps/web/package.json`.

**Problem (Codex):** `setup.ts:3` does `import type { AxeResults } from "axe-core"`
but `axe-core` is only an indirect dep via `vitest-axe`. Direct imports
should be declared.

**Decision:** Add `axe-core` to `devDependencies` in `apps/web/package.json`
at the same version vitest-axe resolves to. Use `npm install --save-dev axe-core`
to regenerate package-lock.json.

```json
"devDependencies": {
  "axe-core": "^4.10.0",  // match resolved version
  ...
}
```

**Test:** `cd apps/web && npm ci` and `npm run typecheck` still clean.

**Commit:** `fix(ui): batch 15 reviewer pass — declare axe-core direct devDependency`

---

## C5 (Critical, archive) — already handled by `72e04ce` revert

The premature archive commit `1059351` was reverted in `72e04ce`. The brief
has been restored to `.ccg/tasks/batch-15-phase-d-a/brief.md`.

Round-2 archive will happen AFTER all fixer rounds complete and reviewers
APPROVE. SKIP this as a fix commit — it's already done.

---

## W1 (Warning) — Pill blanket aria-live noise

**File:** `apps/web/src/components/ui/Pill.tsx`.

**Problem (Opus):** Every Pill gets `role="status" aria-live="polite"` — screen
readers announce every label (`CURRENT CHAMPION`, `FEATURED`, `RUN ID:` etc).
Should only apply to status pulses (RUNNING/COMPLETED/FAILED).

**Decision (Claude):** Gate on `props.pulse` OR add a new `live?: boolean`
prop. Prefer the latter for explicitness. Default `live` to `false`. Existing
call sites that need live (RunTable status pill, BacktestStudioTab queue
pill) opt in via `<Pill pulse live ...>` or `<Pill live ...>`.

```tsx
type PillProps = {
  tone: PillTone;
  size?: PillSize;
  pulse?: boolean;
  live?: boolean;  // NEW: gate aria-live to opt-in
  children: ReactNode;
};

// In render:
const liveProps = live || pulse
  ? { role: "status", "aria-live": "polite" as const }
  : {};
return <span {...liveProps} ...>{children}</span>;
```

Audit call sites: identify pills that ARE status indicators (pulse=true
already, or in features/* representing run status). Add `live` to those.
Leave static-label pills alone.

**Test:** `apps/web/src/test/axe.test.tsx` still passes; existing pill tests
verify default-no-aria-live for static labels.

Add 1 new vitest case: `Pill default has no role/aria-live; Pill with pulse
adds them; Pill with live adds them`.

**Commit:** `fix(ui): batch 15 reviewer pass — gate Pill aria-live on pulse/live opt-in`

---

## W2 (Warning) — `<div id="main-content">` not landmark

**File:** `apps/web/src/pages/ResearchConsolePage.tsx` around line 65.

**Problem (Codex):** Skip-link target is a `<div>` — screen readers treat it
as generic. Should be `<main>` (semantic HTML5) or add `role="main"`.

**Decision:** Change to `<main id="main-content" ...>`. Single change.

**Test:** `apps/web/src/test/axe.test.tsx` may already catch this via
`landmark-unique` / `region` rules; verify still passes (likely improves).

**Commit:** `fix(ui): batch 15 reviewer pass — promote main-content div to <main> landmark`

---

## W3 (Warning) — mypy --strict CI unverified

**File:** `pyproject.toml`, possibly new `[tool.mypy]` section.

**Problem (Opus):** CI gate runs `mypy --strict src/atlas20/api/` but no local
verification; codebase has never been type-checked at strict before; will
likely fail.

**Decision (Claude):** Two-step pragmatic approach:
1. Run `mypy --strict src/atlas20/api` locally; count errors.
2. If errors > 50, scope down CI to `mypy src/atlas20/api/schemas.py
   src/atlas20/api/settings.py src/atlas20/api/_metrics.py` (the most-typed
   modules) and add a `[tool.mypy]` section with reasonable overrides
   (`disallow_untyped_defs = true`, but `disallow_any_explicit = false` and
   per-module overrides for `slowapi.*`, `apscheduler.*`, `weasyprint.*` as
   `ignore_missing_imports = true`).
3. If errors < 50, fix them inline — annotate untyped functions, etc.

The goal: green CI on first push. Update `.github/workflows/ci.yml` mypy job
to match whatever scope landed.

**Test:** `make typecheck` (or direct `mypy ...`) green locally before commit.

**Commit:** `fix(api): batch 15 reviewer pass — mypy strict scope + per-module overrides for green CI`

---

## W4 (Warning) — docker-compose missing dev seed step

**File:** `docker-compose.yml`, `README.md`.

**Problem (Opus):** First `docker compose up` → empty data/ volume → no DB →
500s on every read.

**Decision:** Add to README quickstart: after `docker compose up -d`, run
`docker compose exec backend python -m atlas20.api.seed` to seed initial
fixture data.

Also add a note in `docker-compose.yml` as a comment near the backend service
pointing to the seed step.

**Test:** docs only.

**Commit:** `docs(infra): batch 15 reviewer pass — document docker compose seed step`

---

## W5 (Warning) — W7 partial: compare + universe tabs underspecified

**Files:** `apps/web/src/features/compare/StrategyCompareTab.test.tsx`,
`apps/web/src/features/universe/UniverseHealthTab.test.tsx`.

**Problem (Codex):** W7 state-coverage was added for most tabs but compare
only asserts fallback visibility during loading (not error/empty), and
universe only covers refresh mutation failure (not tab-level loading/error/empty).

**Decision (Claude):** Add the missing state-coverage cases:

- StrategyCompareTab: loading state (Skeleton visible), error state
  (ErrorBanner visible + retry), empty state (when selections=[]).
- UniverseHealthTab: tab-level loading (3 queries Skeleton), tab-level error
  (ErrorBanner), tab-level empty (when timeline empty + sources empty).

Use the existing mock pattern from BacktestStudioTab.test.tsx state tests.

**Test:** ~6 new vitest cases (3 per tab). Frontend climbs from 150 to ~156.

**Commit:** `test(ui): batch 15 reviewer pass — complete W7 state coverage for compare + universe tabs`

---

## Procedure

10 atomic commits in order C1 → C2 → C3 → C4 → W1 → W2 → W3 → W4 → W5.
(C5 already handled by revert `72e04ce`; no commit needed.)

That's 9 commits total.

After each: `python -m pytest tests/ -x -q` green (327). Frontend `npm test`
green; final count ~156. `npm run typecheck && npm run lint` clean.

If C3 Dockerfile fix requires `docker build` validation and docker isn't
available, note in commit body.
If W3 mypy fix surfaces > 50 errors, narrow CI scope per the decision and
document remaining work for a follow-up batch.

## Report

- 9 commit hashes (or note skips/deviations)
- Final backend test count (327 expected)
- Final frontend test count (~156 expected)
- mypy + ruff status
- Docker build status (attempted/skipped + reason)
- Any deviations (Claude triages)
</TASK>
