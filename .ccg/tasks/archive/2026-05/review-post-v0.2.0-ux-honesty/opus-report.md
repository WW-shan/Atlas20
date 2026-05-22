# Opus Review — Post v0.2.0 UX Honesty + FE↔BE Wiring

**Reviewer:** Claude Opus 4.7 (feature-dev:code-reviewer subagent)
**Date:** 2026-05-22

> Note: Subagent's system reminder prohibited writing report files. Findings returned inline to dispatcher and saved here by parent for the cross-validation record.

---

**Verdict:** REQUEST_CHANGES
**Score:** 62/100
**Counts:** 5 Critical · 9 Warning · 2 Info

## Findings Table

| ID | Sev | File:Line | Description | Status | Fix Direction | Schema Δ |
|---|---|---|---|---|---|---|
| C1 | Critical | `OverviewTab.tsx:160-161,171,175` | Equity overlay legend hardcoded `"ATLAS Adaptive v3"` / `"BTC Benchmark"` independent of `champion.strategy`. Real backend champion is `MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK`. | CONFIRMED | Replace literals with `{champion.strategy}` + BTC_BENCHMARK display; pass labels into `<OverlayLineChart lines>`. | No |
| C2 | Critical | `OverviewTab.tsx:184` | Rebalance subtitle hardcoded `"weekly"`; `champion.rebalance_frequency` is `None` from `_build_champion` (overview.py:117). | CONFIRMED | Backend: populate `rebalance_frequency` from selection_history cadence or strategy slug. Frontend: render `champion.rebalance_frequency ?? "—"`. | Yes |
| C3 | Critical | `OverviewTab.tsx:131-155` + `overview.py:185-187,200` | YTD range tabs all `disabled`; backend returns empty series when YTD slice empty. `OverlayLineChart` renders blank SVG. | CONFIRMED | Make tabs functional OR remove tablist; explicit empty-state in `OverlayLineChart`. | Maybe |
| C4 | Critical | `OverviewTab.tsx:94-103` + `overview.py:273-296` | Headline `aum.current` = SUM across strategies; sparkline = champion-only. Two scales juxtaposed. | CONFIRMED | Drop sum and show champion-only, or split into two cards. | No |
| **N1** | **Critical** | `OverlayLineChart.tsx:58-67` | Empty-series fallback renders `<svg>` with no children/text — indistinguishable from loading. Compounds C3. | NEW | Centered `<text>` "No data in selected range" or `<EmptyState>` peer when `series.length === 0`. | No |
| W1 | Warning | `OverviewTab.tsx:234-235` | "Last sync: 18s ago" hardcoded; no `last_sync_seconds` field. | CONFIRMED | Add `last_sync_seconds` to `OverviewPayload` from `app_runs/manifest.json` mtime. | Yes |
| W2 | Warning | `OverviewTab.tsx:131-155` | Range tabs `role="tab"` despite `disabled`+`cursor:default`. A11y misleading. | CONFIRMED | Drop `role="tab"` or implement range switching. | Maybe |
| W3 | Warning | `OverviewTab.tsx:74-76` | Hero renders raw `champion.strategy` slug. | CONFIRMED | Add `display_name` to `ChampionSummary`. | Yes |
| W4 | Warning | `StrategyCompareTab.tsx:21-30` | `DEFAULT_SELECTIONS` + `__TEST_DEFAULT_SELECTIONS` export used only by test. | CONFIRMED | Delete both; refactor tests via `initialSelections` literal. | No |
| W5 | Warning | `StrategyCompareTab.tsx:34-38,47` | `PRESET_COMPARE_IDS` duplicates backend `_resolve_strategy_ids` alias map. | CONFIRMED | Remove map; rely on backend aliases. | No |
| W6 | Warning | `StrategyCompareTab.tsx:117-121` | `fallbackCompare` as `initialData` AND in `data ?? fallbackCompare`; fake ATLAS=+1247% values render under ErrorBanner. | CONFIRMED | Remove `initialData`; show ErrorBanner + empty-state peer. | No |
| **N2** | **Warning** | `ReportsExportsTab.tsx:207` + `lib/api.ts:155-176` | `NewReportModal` falls back to `fallbackOptions.presets` (fake names) when `/api/options` errors → `generateReport` sends fake strategy → silent `warnings: ["no completed run available"]` toast, no banner. | NEW | Gate modal on `options.isSuccess`; or seed `fallbackOptions` from real `config/*.yaml` slugs. | No |
| **N3** | **Warning** | `OverviewTab.test.tsx:12` | Test asserts `getAllByText("ATLAS Adaptive v3").length >= 1`. Only source is hardcoded legend lines 160/171 → fixing C1 breaks the test. | NEW | After C1 fix, switch to `getByRole("heading", { name: champion.strategy })`. | No |
| **N4** | **Warning** | `data_access/universe.py:31` + `services.py:540-548,598-605` + `data_access/compare.py:217-240` | Empty `data/processed/` (untracked in 5a15f77) → universe timeline, alerts, compare's universe loader silently fall back to mock. User sees fake "BNB price gap" alerts dated 2026-05-18. | NEW | Add `data_state: "real" \| "fallback"` discriminator to affected payloads; UI shows "demo data" banner. | Yes |
| I1 | Info | `ReportsExportsTab.tsx:40` | `useState(fallbackFeaturedDigest.defaultFormat)` never resyncs when real `featured.data.defaultFormat` differs. | CONFIRMED | `useEffect(set, [featured.data?.defaultFormat])`. | No |
| I2 | Info | `BacktestStudioTab.test.tsx:33,84` | Tests pivot on synthetic `btk_0142` literal. | CONFIRMED | Reference `fallbackRunDetail.run_id` instead. | No |

## Edge-case sweep

- **Empty `data/processed/`**: Overview survives (uses `report_root`; regime falls back NEUTRAL). Universe/Compare/Alerts silently mock → **N4**.
- **Champion equity ending pre-YTD-anchor**: `_build_equity_overlay` → `{series:[], range:"YTD"}`; `ytdReturn=0.0`, `winRate=0.0`. Hero shows "+0.00%" — honest but indistinguishable from flat year. → **N1** + C3.
- **`_pick_champion` with only BTC_BH**: BTC becomes champion → atlas == btc → both lines overlay at 0% identically. No crash, visually broken.
- **`/api/compare` 500 on real ids**: ErrorBanner shows but fake ATLAS=+1247% chart/metrics persist underneath → W6.
- **Run/queue/options 500**: `useQuery` propagates `isError` correctly except W6 case.
- **Universe/Reports/History tests**: assert mock-derived counts (9 sources, 6 alerts, 5 OPEN, 6 archive cards). Would FAIL against real backend. Out-of-scope per brief but flagged for v0.3.

## Schema extensions required

- `C2`: `ChampionSummary.rebalance_frequency` (populate; field exists)
- `W1`: add `OverviewPayload.last_sync_seconds: int`
- `W3`: add `ChampionSummary.display_name: str`
- `N4`: add `data_state: Literal["real","fallback"]` discriminator to `UniverseTimelinePayload`, `DataAlert[]`, `ComparePayload`

## Summary

REQUEST_CHANGES. 12/12 known CONFIRMED. 4 new: 1 promoted Critical (N1 — silent blank chart compounds C3), 3 Warning (N2 fake-preset leak, N3 test locks C1, N4 demo-data silent substitution). Ship blocked on C1-C4 + N1. W3-W6 + N2-N4 belong in same B23 batch — same files. Test-fix (N3) must accompany C1.
