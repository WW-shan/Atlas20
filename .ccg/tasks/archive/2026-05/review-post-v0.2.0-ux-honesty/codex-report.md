# Codex Review — Post v0.2.0 UX Honesty

**Note:** Codex completed the review but did not write this file directly (cited a read-only-access interpretation of the prompt). This file was saved by the dispatcher as a fallback from codex's stdout.

**Session ID:** 019e4c3c-0d10-7d11-acc9-065b3f86eca9
**Date:** 2026-05-22

---

**Verdict:** REQUEST_CHANGES
**Score:** 56/100
**Counts:** Critical 5, Warning 8, Info 2

## Findings Table

| id | file:line | description | fix direction | needs backend schema change? |
|---|---:|---|---|---|
| C1 CONFIRMED | `OverviewTab.tsx:160,171` | Overlay labels still hardcode `ATLAS Adaptive v3`; champion is payload-driven at `:75`. | Derive label from `champion.strategy`; consider line metadata. | Optional |
| C2 CONFIRMED | `OverviewTab.tsx:184` | Rebalance subtitle hardcodes `weekly`. | Return/render real rebalance cadence. | Yes |
| C3 CONFIRMED | `overview.py:185-187`, `OverviewTab.tsx:131-140` | Old cached reports can return empty YTD series; UI still renders disabled YTD tabs/blank chart. | Anchor to latest available data or render empty state; remove decorative tabs. | Optional |
| C4 REFINED | `OverviewTab.tsx:97-100`, `overview.py:273-295` | Card mixes aggregate current notional with champion-only sparkline; UI hints "champion" but visual grouping remains misleading. | Use aggregate sparkline or split metrics. | No |
| N1 | `services.py:501-507,540-547,598-605,706-712` | Backend catches missing/invalid artifacts and serves mock data, masking empty `data/processed/` and report failures. | Return explicit empty/error state outside dev/test. | Optional |
| W1 CONFIRMED | `OverviewTab.tsx:234-235` | `Last sync: 18s ago` is hardcoded. | Add payload `as_of`/freshness or remove. | Yes |
| W2 CONFIRMED | `OverviewTab.tsx:131-140` | Disabled controls still rendered as range tabs. | Hide until functional or implement ranges. | Optional |
| W3 CONFIRMED | `OverviewTab.tsx:74-75` | Hero prints raw strategy slug. | Add display-name formatter/field. | Optional |
| W4 CONFIRMED | `StrategyCompareTab.tsx:21-30` | Legacy default selections exported only for tests. | Remove test-only production export. | No |
| W5 CONFIRMED | `StrategyCompareTab.tsx:34-38` | Fake display names map to backend aliases. | Use real strategy ids from options only. | No |
| W6 CONFIRMED | `StrategyCompareTab.tsx:117-121` | `fallbackCompare` is `initialData` and remains visible on failed `/compare`. | Use skeleton/empty state; never seed production query with mock payload. | No |
| N2 | `api.ts:328-332`, `reports.py:80-84,111-122` | Frontend types generated report `files` as `ReportEntry[]`; backend returns raw file rows. | Add response schema or fix TS type. | Yes |
| N3 | `api.ts:8,572`, `auth.py:11-19` | Vite API key is browser-visible but used for protected writes. | Use real user auth/BFF for production writes. | No |
| I1 CONFIRMED | `ReportsExportsTab.tsx:40,117-121` | Selected format initializes from fallback and does not sync to real digest default. | Sync after digest load unless user changed it. | No |
| I2 CONFIRMED | `BacktestStudioTab.test.tsx:34,61,84,109` | Tests still center synthetic `btk_0142` fixture. | Prefer real-data invariants and generated ids. | No |

## Positive Notes

- Overview no longer uses frontend fallback on request failure
- Run history/backtest error paths generally show banners instead of mock data
- Backend request models use strict validation for mutating payloads
