# Review brief — Post-v0.2.0 UX honesty + Frontend↔Backend wiring

## Goal

Second-pass review of the Atlas20 research console after v0.2.0 ship. The B16-B22 sweep already wired most surfaces to real backend artifacts, but Claude's first-pass review found 12 issues: 4 known (CHANGELOG `[Unreleased]`) + 8 new. We need an independent cross-validation before dispatching B23/B24 fixers.

## Target

- Branch: `main` (last commit `84d3db1`)
- Range: HEAD (broad sweep, not a specific commit)
- Primary surface: `apps/web/src/features/*` + `src/atlas20/api/data_access/*` + `src/atlas20/api/routes/*` + `src/atlas20/api/schemas.py`

## Review dimensions

1. **UI honesty** — any literal in JSX/TSX (display name, cadence, freshness, run id, range) that lies about real backend state.
2. **Backend contract drift** — Pydantic schema fields the frontend doesn't consume, or `lib/api.ts` types diverged from `schemas.py`.
3. **Mock-fallback leakage** — `fallbackXxx` constants leaking into production paths (initialData, error fallback) and masking backend failures with stale data.
4. **Dead code / unused exports** — constants like `DEFAULT_SELECTIONS`, `PRESET_COMPARE_IDS` that no production path reads.
5. **Disabled-but-rendered controls** — buttons/tabs that carry `role="tab"`/`role="button"` but are visually-only.
6. **Test fixtures shadowing real behavior** — tests asserting mock shape instead of real-data invariants.
7. **Window/anchor edge cases** — `_build_equity_overlay`, `_build_aum`, `_compute_hero_kpi` all anchor on `settings.anchor_date or today()` — what happens when cached reports are older than anchor's YTD start?

## Known findings (already in CHANGELOG `[Unreleased]` + first-pass)

### Critical (CHANGELOG-tracked)

- **C1** `OverviewTab.tsx:160-161,171,175` — equity overlay legend hardcoded `"ATLAS Adaptive v3"` / `"BTC Benchmark"`
- **C2** `OverviewTab.tsx:184` — rebalance subtitle hardcodes `"weekly"`
- **C3** `OverviewTab.tsx:131-155` + `overview.py:173-200` — YTD chart can render empty; range tabs are decorative
- **C4** `OverviewTab.tsx:94-103` + `overview.py:248-296` — Tracked Notional headline (sum) vs sparkline (champion-only) source mismatch

### Warning (new from first-pass)

- **W1** `OverviewTab.tsx:234-235` — "Last sync: 18s ago" hardcoded
- **W2** `OverviewTab.tsx:131-155` — range tabs all disabled, hardcoded active=YTD
- **W3** `OverviewTab.tsx:74-76` — hero renders raw strategy slug
- **W4** `StrategyCompareTab.tsx:21-30` — legacy `DEFAULT_SELECTIONS` + `__TEST_DEFAULT_SELECTIONS` export
- **W5** `StrategyCompareTab.tsx:34-38` — `PRESET_COMPARE_IDS` keyed by fake display names
- **W6** `StrategyCompareTab.tsx:117` — `fallbackCompare` flashes via initialData before real `/api/compare`

### Info

- **I1** `ReportsExportsTab.tsx:40` — `useState(fallbackFeaturedDigest.defaultFormat)` not synced when real digest arrives with different defaultFormat
- **I2** `BacktestStudioTab.test.tsx` — tests pivot on synthetic `btk_0142` (cognitive cost only)

## What reviewers should produce

For each finding (including any net-new ones):

- **Severity** — Critical / Warning / Info
- **File:line** — exact location
- **Description** — 1-2 sentence problem statement
- **Verification of known findings** — for each C1-C4, W1-W6, I1-I2: confirm or refute, with file:line evidence
- **Recommended fix direction** — terse, including whether backend schema needs extension

Final output:
- Score `X/100` overall
- `APPROVE` / `REQUEST_CHANGES` verdict
- Findings table sorted by severity

## Out of scope

- Python test count target (we already track 368 pytest + 163 vitest from v0.2.0)
- B23 fix implementation (this is review-only)
- API route refactors not driven by a Critical/Warning finding
- Style/theme tweaks (Atlas console is "Bloomberg Premium" aesthetic and considered locked)

## Acceptance

Two independent reviewer reports (Opus + codex) on disk under `.ccg/tasks/review-post-v0.2.0-ux-honesty/`:
- `opus-report.md` (Agent A output)
- `codex-report.md` (Agent B output)

If both `APPROVE` with no new Critical/Warning beyond CHANGELOG-tracked → ship B23a as planned.
If new Critical/Warning surfaces → expand B23 scope or block ship.
