# Batch 12 — R3 Redesign Review Audit

Source review: `.ccg/tasks/review-r3-premium-redesign/review.md` (pre-Batches 7-11).

Re-audited 2026-05-20 at HEAD after Batches 7-11 landed. Most findings turned
out to be already-resolved by later batches.

## Audit verdict

| Finding | Original Severity | Verdict | Evidence |
|---|---|---|---|
| C1 `ResearchConsolePage.tsx` inline `["overview"]` key | Critical | STALE | `ResearchConsolePage.tsx:44` uses `qk.overview()` |
| C2 `RunHistoryTab.tsx` missing `initialData: fallbackRunsList` | Critical | STALE | Intentional per Roadmap U7 — DB-backed (Batches 7-10) should not mask real errors with mock |
| C3 `DOWNLOAD ALL · BUNDLE` CTA calls `downloadDigest(format)` | Critical | STALE | `ReportsExportsTab.tsx:86` calls `downloadDigest("bundle")`; test `:75` asserts the bundle arg |
| C4 Non-whitelisted gold usages | Critical | DEFERRED → B15 | All usages route through the `var(--gold)` design token; the concern is aesthetic concentration, not raw hex leakage. Defer to Phase A polish audit |
| W1 SVG mono text missing `font-variant-numeric: tabular-nums` | Warning | STALE | All SVG mono text in `OverlayLineChart.tsx` (3) and `UniverseTimeline.tsx` (4) already set `style={{ fontVariantNumeric: "tabular-nums" }}` |
| W2 Numeric/timestamp displays not wrapped in `.mono` | Warning | DEFERRED → B15 | Partial coverage; full audit fits Phase A polish |
| W3 Backtest workspace uses span `role="tab"` | Warning | STALE | `EquityWorkspace.tsx:31` uses `<button type="button" role="tab">` |
| W4 Backtest strategy select lacks accessible name | Warning | STALE | `ParameterSidebar.tsx:51` sets `aria-label="Strategy preset"` |
| W5 Favorite toggle not wired from `RunHistoryTab` | Warning | STALE | `RunHistoryTab.tsx:160` passes `onToggleFavorite={handleToggleFavorite}` to `<RunTable>` |
| **W6** Query keys partially canonical; `RunHistoryTab` invalidates via inline `["runs", "list"]` tuple | Warning | **FIXED** | `5454036` adds `qk.runs.listAll()` helper; both `setQueriesData` and `invalidateQueries` now route through qk |
| W7 Tab feature tests don't cover loading/error/empty | Warning | DEFERRED → B15 | Phase T (testing pyramid) belongs in Batch 15 |
| W8 Stale legacy CSS after P11 cleanup | Warning | DEFERRED → B15 | Needs CSS dead-code audit; fits Phase A polish |
| W9 `api.test.ts` unnecessary `as unknown` cast | Warning | STALE | No `as unknown` cast present |

## Summary

- 7 / 13 findings stale (resolved by Batches 7-11)
- 1 fixed in this batch (W6)
- 4 deferred to Batch 15 Phase A polish (C4, W2, W7, W8)

## Deferred items checklist for Batch 15

- [ ] **C4** — Gold token concentration audit. Catalog every `var(--gold)`
  usage; decide whether the design token whitelist (champion KPI / hero CTA /
  active state) needs tightening, or whether the current spread is intentional.
- [ ] **W2** — Wrap remaining HTML numeric/timestamp spans in `.mono` (or
  `className="mono"`) for visual consistency. Run a grep for `toFixed`,
  `toISOString`, percentage formatters and verify each renders in a mono
  container.
- [ ] **W7** — Add loading / error / empty state coverage to each tab's
  vitest suite. Specifically: UniverseHealthTab, BacktestStudioTab, click
  through key actions instead of only asserting render. Fits the Phase T
  test-pyramid work.
- [ ] **W8** — CSS dead-code audit: walk `styles/index.css` against actual
  selector usage in the source tree; remove anything orphaned by the P11
  cleanup.

## Verification at HEAD (`5454036`)

- `cd apps/web && npm run test -- --run` → 132 passed
- Backend pytest unchanged at 269
- No new findings introduced
