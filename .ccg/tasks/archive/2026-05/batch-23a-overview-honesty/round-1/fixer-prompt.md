# Batch 23a — Fixer Prompt (Round 1)

Round 1 cross-validation: **Opus APPROVE 92/100** + **Codex REQUEST_CHANGES 84/100**. Merged findings below. **Every finding gets its own commit** per CCG protocol Step 5.

Fix in this order (each is independent; no inter-dependencies).

---

## F1 — Warning — Aria-labels hardcoded YTD/year-to-date

**Source:** codex W1
**File:line:** `apps/web/src/features/overview/OverviewTab.tsx:136,147`
**Problem:** Two aria-labels still say "YTD" / "year to date" even when `equity_overlay.range === "ALL"` (backend falls back to ALL when YTD slice empty). Screen-reader UX lies.

**Claude's decision:** Derive both aria-labels from payload fields.

**Fix:**
- Line 136: `<Card ariaLabel="Champion equity curve YTD">` → `<Card ariaLabel={`Champion equity curve ${equity_overlay.range}`}>`
- Line 147: `ariaLabel="ATLAS vs BTC equity curve year to date"` → `ariaLabel={`${equity_overlay.atlas_label} vs ${equity_overlay.btc_label} equity curve ${equity_overlay.range}`}`

**Regression test:** Add one assertion to `OverviewTab.test.tsx`: render with a fixture where `equity_overlay.range === "ALL"`, assert the Card and OverlayLineChart aria-labels contain `"ALL"` (not `"YTD"` and not `"year to date"`).

**Commit message:** `fix(web): batch 23a reviewer pass — aria-labels follow equity_overlay.range`

---

## F2 — Warning — Path-traversal bypass in `_compute_last_sync_seconds`

**Source:** codex W2 (security-relevant)
**File:line:** `src/atlas20/api/data_access/overview.py:299-308`
**Problem:** `_compute_last_sync_seconds` does its own `(report_root / latest_txt.read_text()).resolve()` without the `relative_to(report_root)` guard that `_latest_report_dir` (`_common.py:13-31`) already implements. A `latest.txt` containing `../../etc/passwd` (or any escaping path) would let us stat outside the report tree. Mtime alone doesn't leak file contents but it's an unnecessary attack surface and a duplication of safety logic.

**Claude's decision:** Delegate to `_latest_report_dir`. It already returns a path inside `report_root` (or raises). Drop the bespoke pointer-reading.

**Fix:**

Replace the function body with:

```python
def _compute_last_sync_seconds(report_root: Path) -> int:
    try:
        target_dir = _latest_report_dir(report_root)
        return max(0, int(time.time() - target_dir.stat().st_mtime))
    except (FileNotFoundError, ValueError):
        return 0
```

Drop the explicit `latest_txt.exists() / read_text / resolve()` block. Drop the `target.exists()` re-check (`_latest_report_dir` already validates the resolved path exists and is inside `report_root`).

**Regression test:** Update `tests/test_overview_data_access.py:test_compute_last_sync_seconds_uses_latest_pointer_and_missing_files`:
- Add a test case that writes `latest.txt` containing `"../escape"` (or any escaping path); expect `_compute_last_sync_seconds` returns `0` (caught `ValueError` from `_latest_report_dir`).
- Verify the existing happy + missing-tree paths still pass.

**Commit message:** `fix(api): batch 23a reviewer pass — _compute_last_sync_seconds reuses _latest_report_dir path-traversal guard`

---

## F3 — Warning — Edge-case tests thin

**Source:** opus W1 + codex W3 (same finding, different lens)
**File:line:** `tests/test_overview_data_access.py:196-220`
**Problem:** Brief Tests #5 (`_compute_last_sync_seconds` broken-pointer subcase) marked WEAK; codex flagged additional missing: clock skew, NaN-only YTD slice, duplicate rebalance dates.

**Claude's decision:** Backfill targeted tests. The production code already handles these cases (Opus's edge-probe pass confirmed). This commit just locks them with assertions.

**Fix:** Add four new test functions to `tests/test_overview_data_access.py`:

1. `test_parse_cadence_dedupes_rebalance_dates` — synthetic `selection_history` with duplicate `rebalance_date` rows for the same strategy (e.g. two rows on 2026-01-01, two on 2026-01-15, two on 2026-01-29); assert `_parse_cadence(...)` returns "Biweekly".
2. `test_compute_last_sync_seconds_clock_skew_returns_non_negative` — monkeypatch `time.time` to return a value smaller than the report dir's mtime; assert result is `0` (via `max(0, ...)`).
3. `test_build_equity_overlay_nan_in_ytd_slice_uses_dropna` — construct `equity_curves_df` with NaN values in the YTD window; assert the returned `series` is non-empty AND no NaN values leak through.
4. (Already covered by F2's regression test, but ensure it stays in this file) `test_compute_last_sync_seconds_rejects_escaping_pointer` — implements the F2 regression.

Total: +3 new tests on top of F2's +1, raising pytest count from 375 → 379.

**Commit message:** `test(api): batch 23a reviewer pass — backfill edge-case tests for cadence/clock-skew/nan/escaping-pointer`

---

## F4 — Info — Order-matters comment on cadence slug tokens

**Source:** opus I1
**File:line:** `src/atlas20/api/data_access/overview.py:265`
**Problem:** `_parse_cadence` slug-token list order has `_weekly_` checked before `_biweekly_`. Substring search is safe in practice (`_biweekly_` does not contain `_weekly_` as a substring due to the `b` separator), but the precedence is implicit and a future maintainer might reorder them.

**Claude's decision:** Add a one-line comment.

**Fix:** Above the `for token, label in [...]` line, add:

```python
# Token order: substring check; `_biweekly_` correctly doesn't contain `_weekly_`
# because of the `b` separator. Keep biweekly first to be explicit.
```

Optionally swap the order to put `_biweekly_` first to make the precedence visually unambiguous. **Pick whichever change is smaller** — if the comment alone is clearer, leave the order. If swapping is cleaner, swap and drop the comment.

**No regression test needed** (style only).

**Commit message:** `refactor(api): batch 23a reviewer pass — clarify _parse_cadence slug token precedence`

---

## Per-commit verification

After each fix commit:

1. `python -m pytest tests/ -x -q` — green
2. (F1 only) `npm --prefix apps/web run typecheck` + `npm --prefix apps/web test -- --run --reporter=basic` — green
3. `git status --short` — clean

Final state expected:
- 4 new commits (F1-F4)
- pytest: 375 → 379 (+4 from F3 + F2's regression test that's accounted in F3)
- vitest: 168 → 169 (+1 from F1 regression test)

**Items NOT to fix** (both reviewers agreed acceptable):
- `mock_data.py` touch (Opus I2 + codex I1) — justified for schema-validation compatibility, no action.

---

## Output expected from fixer

Print final summary with:
- 4 commit hashes (F1 → F2 → F3 → F4 order)
- pytest count after each
- vitest count after F1
- Any deviations from this plan
