# Batch 23a — Fixer Prompt (Round 2 Follow-up)

Round 2 cross-validation: **Opus APPROVE 96/100** + **Codex REQUEST_CHANGES 90/100**. Codex's only open finding is F3-NaN-YTD subcase. One commit needed.

---

## F5 — Warning (carryover from F3) — NaN-only YTD slice test missing

**Source:** codex round-2 W1 (treating F3 as STILL OPEN)
**File:line:** `tests/test_overview_data_access.py:274-288` — `test_build_equity_overlay_nan_in_ytd_slice_uses_dropna`

**Problem:** The existing test puts a single NaN row in the middle of a 3-row series; `dropna()` filters it out and the remaining 2 finite rows still fall in the YTD window. This locks the "dropna skips bad rows" behavior but does NOT exercise the path where the entire YTD slice becomes empty due to NaN filtering and the function falls back to `range="ALL"` using historical (pre-YTD) data.

The fall-back-to-ALL branch is currently locked only by the temporal-filter test (`test_build_equity_overlay_falls_back_to_all_when_ytd_empty` at `:223-236`), where YTD-emptiness comes from the data being outside the YTD date window. The NaN-induced YTD-emptiness path isn't separately pinned.

**Claude's decision:** Add ONE new test alongside the existing NaN test. Do not modify the existing test (Opus confirmed it correctly locks the single-NaN-row behavior).

**Fix:** Add `test_build_equity_overlay_falls_back_to_all_when_ytd_rows_are_all_nan` to `tests/test_overview_data_access.py` immediately after `test_build_equity_overlay_nan_in_ytd_slice_uses_dropna`.

The test should:

1. Build an `equity_curves_df` with rows spanning across a year boundary, e.g. index `["2025-10-31", "2025-11-30", "2025-12-31", "2026-01-31", "2026-02-28"]`.
2. Set ALL YTD-range rows (2026-01-31, 2026-02-28) to have NaN in either `atlas` or `btc` column.
3. Set the pre-YTD rows (2025-Q4) to finite values.
4. Call `_build_equity_overlay(frame, champion, date(2026, 2, 28))`.
5. Assert `overlay["range"] == "ALL"` (the YTD slice is empty after dropna, so fallback triggers).
6. Assert `overlay["series"]` is non-empty (the pre-YTD finite rows survived).
7. Assert all points are finite (`pd.notna(point["atlas"]) and pd.notna(point["btc"])`).

Total: +1 new test, raising pytest count from 379 → 380.

**Commit message:** `test(api): batch 23a reviewer pass — lock NaN-only YTD slice triggers fall-back-to-ALL`

---

## Per-commit verification

After the fix commit:

1. `python -m pytest tests/ -x -q` — green (380 expected)
2. `git status --short` — clean

Final state expected:
- 1 new commit (F5) stacked on `6b139b2`
- pytest: 379 → 380

**Items NOT to change:**
- The existing `test_build_equity_overlay_nan_in_ytd_slice_uses_dropna` stays — it correctly locks the single-NaN-row dropna behavior.
- No frontend changes.
- `mock_data.py` still untouched.

---

## Output expected from fixer

Print:
- Commit hash (F5)
- pytest count after F5
- Any deviations
