# Opus Report — Batch 23a Round 1 Cross-Validation

**Target commit:** `dd640af` on `feat/b23a-overview-honesty`
**Reviewer:** Agent A (Opus 4.7 1M)
**Date:** 2026-05-22

---

## Verdict: APPROVE
## Score: 92/100

## Summary

Builder satisfied all brief deliverables. All 13 test items from the brief have concrete passing tests. All 4 edge probes (clock skew, broken latest.txt pointer, empty equity series, `_format_display_name` no-prefix fallback) handled correctly by the implementation. The `mock_data.py` out-of-scope touch is **justified** — without it, `services._load_overview_payload` would raise `ValidationError` on the new required schema fields when falling back. Tablist removal is clean. Frontend tests assert payload-driven shape, not hardcoded literals. Backend test delta +7, frontend +5.

## Findings

| id | severity | file:line | description | fix direction | regression test? |
|----|----------|-----------|-------------|---------------|------------------|
| W1 | Warning | `tests/test_overview_data_access.py:212` | `test_compute_last_sync_seconds_uses_latest_pointer_and_missing_files` covers happy + wholly-missing-tree paths but NOT the brief's "broken pointer" subcase (latest.txt points at non-existent dir). The `_latest_report_dir` fallback branch is exercised only implicitly. | Add an assertion: write `latest.txt` with `"does_not_exist"` content; expect non-negative int via fallback. | yes |
| I1 | Info | `src/atlas20/api/data_access/overview.py:265` | `_parse_cadence` slug token order: `_weekly_` checked before `_biweekly_`. Substring is safe (`_biweekly_` doesn't contain `_weekly_` due to `b` separator), but precedence is implicit. | Add one-line comment: "order matters: substring check; `_biweekly_` correctly doesn't contain `_weekly_`". | no |
| I2 | Info | `src/atlas20/api/mock_data.py:9` | `display_name` literal `"Momentum Lead Top1 All 14D Stop11 Confirm2 Btc Park"` hand-written; if `_format_display_name` title-casing changes, this drifts silently. | Either compute via production helper, or add unit test pinning the equality. Acceptable as-is. | no |

## Brief Test Coverage

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | `_format_display_name` 4 stable strings | COVERED | `test_overview_data_access.py:182-189` |
| 2 | `_parse_cadence` slug match → Biweekly | COVERED | `:192-193` |
| 3 | `_parse_cadence` 14d median → Biweekly | COVERED | `:196-204` |
| 4 | `_parse_cadence` returns None | COVERED | `:207-209` |
| 5 | `_compute_last_sync_seconds` nonzero/zero | **WEAK** | `:212-220` — broken-pointer subcase not pinned (see W1) |
| 6 | `_build_equity_overlay` YTD→ALL fallback | COVERED | `:223-236` |
| 7 | `_build_equity_overlay` labels | COVERED | `:239-252` |
| 8 | Hero renders `display_name` | COVERED | `OverviewTab.test.tsx:18-31` |
| 9 | Legend uses `atlas_label` not literal | COVERED | `:33-47` |
| 10 | Rebalance cadence from payload | COVERED | `:49-58` |
| 11 | `formatRelativeAge` boundaries 59/60/3599/3600 | COVERED | `:60-72` |
| 12 | Empty-state copy on empty series | COVERED | `:74-82` |
| 13 | Line-12 uses payload field | COVERED | `:12-16` |

## Edge Probe Results

- `_format_display_name` no-prefix fallback (`MOMENTUM_LEAD_TOP1_ALL_14D_...`) → produces `"Momentum Lead Top1 All 14D Stop11 Confirm2 Btc Park"`. ✅
- `_parse_cadence` case-insensitivity: code lowercases before substring search. ✅
- `_compute_last_sync_seconds` clock skew: `max(0, int(...))` guarantees non-negative. ✅
- `_compute_last_sync_seconds` broken pointer: `target.exists()` False → falls through to `_latest_report_dir`; on total miss returns 0. ✅ (untested — see W1)
- `_build_equity_overlay` empty series entirely: guarded at line 191-192 with explicit `ValueError` before YTD logic. ✅
- `_build_equity_overlay` NaN in YTD slice: NaN filtered by `dropna()` at line 190 BEFORE YTD slicing. ✅
- `_parse_cadence` duplicate dates: `drop_duplicates()` at line 283 eliminates dupes. ✅
- Tablist removal: no `role="tab"` / `role="tablist"` / range-button JSX remains. ✅
- `mock_data.py` touch JUSTIFIED — required for `OverviewPayload.model_validate(mock_data.fallback_overview)` not to raise on new required fields.

## Final Statement

APPROVE. 0 critical, 1 warning (test gap), 2 info. All 13 brief test items have evidence; 12 COVERED outright, 1 WEAK (item #5 missing broken-pointer subcase). Builder stayed in scope with one justified extra-file touch (`mock_data.py`) for service-layer fallback compatibility.
