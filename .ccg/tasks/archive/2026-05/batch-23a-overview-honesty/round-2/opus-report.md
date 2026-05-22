# Opus Report — Batch 23a Round 2 Cross-Validation

**Target range:** `dd640af..HEAD` on `feat/b23a-overview-honesty`
**Reviewer:** Agent A (Opus 4.7 1M)
**Date:** 2026-05-22

---

## Verdict: APPROVE
## Score: 96/100

## Per-finding status

| ID | Status | Evidence at HEAD |
|----|--------|-----------------|
| F1 | RESOLVED | `apps/web/src/features/overview/OverviewTab.tsx:136` card aria: `Champion equity curve ${equity_overlay.range}`; `:147` chart aria: `${equity_overlay.atlas_label} vs ${equity_overlay.btc_label} equity curve ${equity_overlay.range}`. Both payload-driven. Regression test at `OverviewTab.test.tsx:49-67` covers `range: "ALL"`. |
| F2 | RESOLVED | `src/atlas20/api/data_access/overview.py:299-304` calls `_latest_report_dir(report_root)` and stat's the returned path. `_common.py:21-29` enforces `relative_to(resolved_root)`; escaping pointer raises `ValueError` caught at `:303` → returns 0. Duplicated validation gone. |
| F3 | RESOLVED | 4 new tests in `tests/test_overview_data_access.py`: (a) `:241-249` `test_compute_last_sync_seconds_clock_skew_returns_non_negative` via monkeypatched `time.time`; (b) `:252-255` `test_compute_last_sync_seconds_rejects_escaping_pointer` via `../escape`; (c) `:207-222` `test_parse_cadence_dedupes_rebalance_dates` — without dedupe, diff-median of `[01,01,15,15,29,29]` would yield 0 → "Weekly"; test asserts "Biweekly"; (d) `:274-288` `test_build_equity_overlay_nan_in_ytd_slice_uses_dropna` injects NaN, asserts finite. All assert intended branches, not smoke-pass. |
| F4 | RESOLVED | `src/atlas20/api/data_access/overview.py:266-273` token order now lists `_biweekly_` BEFORE `_weekly_`. Pinned by existing `test_parse_cadence_uses_slug_token` at `:192-193`. |

## Regression sweep

- **F1 aria-label change:** Pre-existing test at `OverviewTab.test.tsx:127-130` uses regex `/equity curve YTD/`. Under `fallbackOverview` (range "YTD"), new aria is `"Momentum Lead Top1 All 14D Stop11 Confirm2 Btc Park vs BTC Benchmark equity curve YTD"` — regex still matches. No weakening.
- **F2 directory-vs-file mtime:** `_latest_report_dir` returns the resolved directory. `Path.stat().st_mtime` on a directory returns the directory's own mtime, which updates when entries are added/replaced — actually a tighter "last sync" proxy than any single CSV's mtime. Clock-skew test calls `os.utime(report_dir, ...)`, confirming end-to-end. No semantic regression.
- **F3 new-test rigor:** Each new test would FAIL under mutation: drop `max(0, ...)` → clock-skew fails; drop `drop_duplicates()` → dedupe fails (returns "Weekly"); remove `relative_to` guard → escape fails with different exception; remove `.dropna()` → NaN test fails on `notna` assertion.
- **F4 reorder:** Pinned by `test_parse_cadence_uses_slug_token` `:192-193` — still passes.

## Broader checks

- `src/atlas20/api/mock_data.py:9` unchanged from round 1 (file not modified in any of the 4 fixer commits). ✅
- Backend: `tests/test_overview_data_access.py` +4 tests (clock skew, escaping pointer, dedupe, NaN-in-YTD). System total 375 → 379. ✅
- Frontend: `OverviewTab.test.tsx` +1 test ("uses equity overlay range in aria labels"). System total 168 → 169. ✅

## NEW issues

**None.**

## Summary

APPROVE — 96/100. All 4 round-1 findings RESOLVED with file:line evidence at HEAD. Fixer commits are tight (1 file each except the test commit, no scope creep). `mock_data.py` correctly untouched. Test count deltas match the brief (+4 pytest, +1 vitest). All 4 new pytest cases genuinely exercise targeted branches (verified via mutation reasoning). No regressions: existing `/equity curve YTD/` vitest regex still matches the new payload-driven aria label under `fallbackOverview`. Cross-validation complete.
