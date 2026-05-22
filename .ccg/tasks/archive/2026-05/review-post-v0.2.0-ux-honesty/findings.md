# Cross-validation matrix — Post v0.2.0 review

**Reviewers:** Opus 4.7 (Agent A) + codex (Agent B, session `019e4c3c-0d10-7d11-acc9-065b3f86eca9`)
**Date:** 2026-05-22
**Result:** Both REQUEST_CHANGES — Opus 62/100, codex 56/100

## Agreement on known findings

All **12/12** known findings (C1-C4, W1-W6, I1-I2) CONFIRMED by both reviewers with file:line evidence. C4 refined by codex (visual-grouping framing) — converges with Opus's "two scales juxtaposed" framing.

## Net-new findings — cross-mapped

| Merged ID | Sev | Source | File:Line | Description |
|-----------|-----|--------|-----------|-------------|
| **N1-blank-chart** | Critical | Opus only | `OverlayLineChart.tsx:58-67` | Empty-series fallback renders blank `<svg>` with no copy. Compounds C3 into a silent visual void. |
| **N2-mock-leak** | Critical | **Opus N4 + codex N1 (same defect, broader scope)** | `services.py:501-507,540-547,598-605,706-712` + `data_access/universe.py:31` + `data_access/compare.py:217-240` | Backend silently substitutes `mock_data.fallback_*` for missing `data/processed/` artifacts across overview/compare/universe/data-alerts. Frontend has zero signal. |
| **N3-report-contract** | Warning | codex only | `lib/api.ts:328-332` ↔ `routes/reports.py:80-84,111-122` | TS types `files` as `ReportEntry[]`; backend returns raw file rows. Schema drift — runtime mismatch waiting to happen. |
| **N4-api-key-auth** | Warning | codex only | `lib/api.ts:8,572` ↔ `api/auth.py:11-19` | `VITE_*` env vars are browser-visible; using one to gate protected writes is broken auth model. |
| **N5-fake-presets** | Warning | Opus only | `ReportsExportsTab.tsx:207` + `lib/api.ts:155-176` | `NewReportModal` falls back to `fallbackOptions.presets` when `/api/options` errors → user picks fake name → `generateReport` returns silent warning, no banner. |
| **N6-test-locks-C1** | Warning | Opus only | `OverviewTab.test.tsx:12` | `getAllByText("ATLAS Adaptive v3")` asserts ON the hardcoded literal that C1 fixes. Test will fail when C1 ships unless co-updated. |

## Severity rollup

- Critical: 4 known (C1-C4) + 2 new (N1-blank-chart, N2-mock-leak) = **6**
- Warning: 6 known (W1-W6) + 4 new (N3-N6) = **10**
- Info: 2 known (I1-I2) = **2**

## Verdict

**REQUEST_CHANGES.** Both reviewers agree the console ships with multiple UI lies and silent fallback paths. The mock-fallback substitution (N2-mock-leak) is the most consequential — it lets the demo build look like a working real-data console even with empty `data/processed/`, which is exactly the state any fresh clone now has after commit `5a15f77`.

## Recommended batch plan

### B23a — Overview UX honesty + chart empty state (1 batch, single tab)

**Scope (~150 LOC):**
- C1 — equity overlay legend from `champion.strategy` + benchmark constant
- C2 — backend populates `champion.rebalance_frequency`; frontend renders it
- C3 — wire YTD/1M/3M/1Y/ALL range tabs OR drop tablist
- N1-blank-chart — `OverlayLineChart` empty-state copy
- W2 — same as C3 follow-through (drop `role="tab"` if not implementing)
- W3 — `ChampionSummary.display_name` backend field
- W1 — `OverviewPayload.last_sync_seconds` backend field
- N6-test-locks-C1 — update `OverviewTab.test.tsx`

**Backend schema delta:** `ChampionSummary.{rebalance_frequency populated, display_name added}`, `OverviewPayload.last_sync_seconds added`.

### B23b — Tracked Notional reality (1 batch, narrow)

**Scope (~40 LOC):**
- C4 — drop sum-headline OR show champion-only headline matching sparkline

### B24 — Demo-data discriminator + Compare cleanup (1 batch, cross-cutting)

**Scope (~120 LOC):**
- N2-mock-leak — add `data_state: Literal["real","fallback"]` discriminator to `UniverseTimelinePayload`, `DataAlert[]`, `ComparePayload`; render "DEMO DATA" badge when fallback
- W4 — delete `DEFAULT_SELECTIONS` + `__TEST_DEFAULT_SELECTIONS`
- W5 — delete `PRESET_COMPARE_IDS`
- W6 — remove `fallbackCompare` from `initialData` + error fallback chain
- N5-fake-presets — gate `NewReportModal` open on `options.isSuccess`, or seed `fallbackOptions` from real preset slugs

### B25 — Contract drift + auth model (1 batch, requires UX decision)

**Scope (~60 LOC):**
- N3-report-contract — align `lib/api.ts ReportEntry` with `reports.py` row shape
- N4-api-key-auth — open decision: full BFF/cookie auth vs documented dev-only API-key + production warning

### Quick wins (any batch)
- I1 — `useEffect` to resync `format` on featured digest load
- I2 — replace `btk_0142` literals with `fallbackRunDetail.run_id`

## Files saved

- `.ccg/tasks/review-post-v0.2.0-ux-honesty/brief.md`
- `.ccg/tasks/review-post-v0.2.0-ux-honesty/opus-report.md`
- `.ccg/tasks/review-post-v0.2.0-ux-honesty/codex-report.md`
- `.ccg/tasks/review-post-v0.2.0-ux-honesty/findings.md` (this file)
