# Batch 15 — Phase D + Phase A + R3 Deferred Polish

Scope: Roadmap Phase D (Docker, CI gates, Makefile, pre-commit, README,
storage docs), Phase A (a11y skip-link, ErrorBoundary, live regions,
axe-core CI), and R3-deferred items from Batch 12 (C4 gold→violet downgrade,
W2 `.mono` wrap audit, W7 tab state coverage, W8 stale CSS cleanup). Closes
the MS-3 production-readiness milestone.

## Cycle summary

| Stage | Commits | Backend | Frontend |
|---|---|---|---|
| Builder (5 commits incl. premature archive) | 5 | 327 → 327 | 132 → 150 |
| Revert of premature archive | 1 | — | — |
| Round-1 reviewer fixes | 10 | 327 → 327 | 150 → 156 |
| Round-2 reviewer fixes | 2 | 327 → 327 | 156 → 156 |
| **Total** | **18** | **327 unchanged** | **132 → 156 (+24)** |

## Reviewer scorecard

| Round | Opus | Codex |
|---|---|---|
| 1 | 62/100 REQUEST_CHANGES (3 Critical / 3 Warning / 5 Info) | 60/100 REQUEST_CHANGES (3 Critical / 3 Warning / 0 scoped Info) |
| 2 (post round-1) | 96/100 APPROVE (1 advisory Warning / 2 Info) | 84/100 REQUEST_CHANGES (1 new Critical — Dockerfile README missing) |
| 3 (post round-2) | 98/100 APPROVE (2 Info — both null findings) | **100/100 APPROVE** |

Discrepancy in round 2 (Opus 96 vs Codex 84) was resolved in codex's favor —
Codex correctly caught the Dockerfile readme metadata issue that Opus missed.

## Builder commits (5)

- `df27b56` — `feat(infra): R15 batch 15 Phase D — Docker, compose, Makefile, pre-commit, CI gates`
- `81e87d1` — `feat(ui): R15 batch 15 Phase A — a11y skip-link, ErrorBoundary, live regions, axe-core CI`
- `8ca10d7` — `feat(ui): R15 batch 15 R3 — C4 downgrade gold to violet for cell selection borders`
- `5750f57` — `test(ui): R15 batch 15 R3 W7 — tab loading/error state coverage`
- `1059351` — `chore: archive ccg task batch-15-phase-d-a` (premature; reverted)

## Revert (1)

- `72e04ce` — `Revert "chore: archive ccg task batch-15-phase-d-a"` — protocol Step 7 requires archive AFTER cross-validation completes, not during builder pass.

## Round-1 fix commits (10) — 3 Critical + 3 Warning + 4 wins from W7/lint

| Commit | Finding |
|---|---|
| `85feafc` | C1 (both) — W2 brief skipped (`.mono` wrap audit; re-audit found 0 unwrapped HTML sites, commit is empty audit-record) |
| `7b910de` | C2 (both) — W8 brief skipped (stale CSS cleanup — 156 LOC removed from `apps/web/src/styles/index.css`) |
| `708c15c` | C3 (both) — Dockerfile editable-install runtime path break (drop `-e` + `[dev]`; runtime no longer copies src) |
| `d225a90` | C4 (Codex) — `axe-core` undeclared direct devDependency (now explicit in package.json) |
| `e8f1280` | W1 (Opus) — Pill blanket aria-live noise (gate on `pulse`/`live` opt-in) |
| `70f396e` | W2 (Codex) — `<div id="main-content">` not landmark (promoted to `<main>`) |
| `3678c33` | W3 (Opus) — mypy --strict CI unverified (narrowed scope to schemas/settings/_metrics + per-module overrides for slowapi/apscheduler/weasyprint/markdown/pandas/yaml) |
| `93417f0` | W4 (Opus) — docker-compose missing dev seed step (documented in README + compose comment) |
| `25009bd` | W5 (Codex) — W7 partial: compare/universe state coverage incomplete (added +6 tests + minimal component state guards) |
| `28f1e50` | codex self-fix — ruff unused-import cleanup to keep CI green after mypy scope wiring |

## Round-2 fix commits (2)

| Commit | Finding |
|---|---|
| `76063bc` | Codex-R2-Critical — Dockerfile builder COPY pyproject.toml + src but missing README.md (pyproject `readme = "README.md"` → pip install metadata failure) |
| `6c6d2d7` | Opus-R2-Warning W3 advisory + Info#2 — document mypy strict-pilot scope intent + atlas20.config follow_imports="skip" rationale in pyproject.toml |

## Notable outcomes

### Phase D
- Multi-stage backend Dockerfile (slim Python 3.11 + weasyprint native deps)
- Multi-stage frontend Dockerfile (node→nginx) with SPA fallback + /api proxy
- `docker-compose.yml` with volume mounts for data/ + reports/
- `Makefile`: `dev`, `test`, `lint`, `typecheck`, `build`, `docker-build`, `backup`, `clean`
- `.pre-commit-config.yaml` with ruff + ruff-format + prettier + eslint
- CI extended with ruff + mypy (scoped strict pilot) + tsc + deploy-stub jobs
- README has 30-min Quickstart pointing at `make dev` / `docker compose up` / seed step
- `docs/operations/storage.md` documents disk-growth expectations + retention

### Phase A
- `ErrorBoundary` class component catches render errors; wraps each tab in `ResearchConsolePage`
- Skip-to-content link as first focusable; targets `<main id="main-content">` landmark
- `Toast` + `Pill` `role="status"` / `aria-live="polite"` opt-in (default off; gated on `live` / `pulse`)
- axe-core in CI via `vitest-axe`; per-tab violation tests (color-contrast disabled in jsdom)
- New `apps/web/src/test/axe.test.tsx` covers all 6 tabs

### R3 deferred
- C4 — gold→violet downgrade for selection borders (Pager active page, RunTable selected row, RunHistoryTab selected card); gold preserved for champion KPI, primary CTAs, FEATURED tag, favorited toggle, chart atlas-line
- W2 — re-audit confirmed all HTML numerics already wrapped via `.mono` ancestor (KpiTile, RunTable td, ComparisonTable td, etc.); no source change required
- W7 — added loading/error/empty state coverage for compare + universe tabs
- W8 — 156 LOC stale CSS removed (`.topbar`, `.sparkline`, `.logic-grid`, `.dashboard-grid`, `.workspace`, `.status-list`, `.hero-summary`, `.overview-grid`, `.metric-grid`, `.text-*`, `.tab-switcher`, etc.); `.topnav-tab--active` kept (borderline gold/featured semantic)

## Outstanding (backlog only)

- Docker build not locally verified — daemon stopped in dev env. CI must validate on first push.
- mypy strict pilot currently covers 3 leaf files (schemas, settings, _metrics). Expanding to data_access/ + repositories/ tracked for post-MS-3.
- nginx security headers (X-Frame-Options, CSP, X-Content-Type-Options) not yet set — flag for Lighthouse pre-tag sweep.

## Cycle verification at HEAD (`6c6d2d7`)

- `python -m pytest tests/ -q` → 327 passed, 2 skipped
- `cd apps/web && npm run test -- --run` → 156 passed
- `cd apps/web && npm run typecheck && npm run lint` → clean
- `git diff --check a6a5733..HEAD` → clean
