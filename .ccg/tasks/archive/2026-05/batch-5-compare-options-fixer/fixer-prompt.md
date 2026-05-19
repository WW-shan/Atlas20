You are the codex FIXER for Atlas20 Batch 5 reviewer findings.

Target commit to amend (via new commits, NOT --amend): `9140815`

Three Warning-level findings from cross-validation (Opus 4.7 code-reviewer):

## Warning #1 — `_as_float` map result discarded (NaN/inf leak)

In `src/atlas20/api/data_access/compare.py:71`, the line:
```python
parsed[column].map(_as_float)
```
returns a Series that is THROWN AWAY. So NaN/inf values that survive
`pd.to_numeric(errors="raise")` (which only raises on non-coercible
strings, not on NaN/inf in source data) pass validation undetected.

The brief explicitly requires "Use Batch-3 `_as_float` to reject NaN/inf".

**Same bug pattern recurs at:**
- `src/atlas20/api/data_access/compare.py:225` (`_load_latest_universe`)
- `src/atlas20/api/data_access/options.py:54` (or wherever the same idiom is)

**Fix:** Re-assign the mapped series. Either:
```python
parsed[column] = parsed[column].map(_as_float)
```
OR call `_as_float` inside a validation loop that raises with column context.

Add a regression test in `tests/test_compare_data_access.py` that synthesizes
a `strategy_summary.csv` with `NaN` in a numeric column and asserts
`load_compare_from_reports` raises ValueError.

## Warning #2 — Extract shared CSV helpers to `_common.py`

The brief said extract when "used in 3+ modules". Currently `overview.py`,
`universe.py`, `compare.py`, and `options.py` all import or duplicate:
- `_as_float`, `_date_string`, `_latest_report_dir`, `_load_date_indexed_csv`,
  `_read_csv` (from `overview.py`)
- `_read_processed_csv` (from `universe.py`)
- `_as_text` (duplicated verbatim in `compare.py:274` AND `options.py:81`)

**Fix:** Create `src/atlas20/api/data_access/_common.py` that hosts these
helpers. Update all four modules to import from `_common`. Remove the
duplicate `_as_text` definitions. Keep public API behavior identical.

Existing tests must still pass — these are private helpers and are tested
via integration through the public `load_*_from_reports` / `_from_processed`
functions, so no test changes should be required.

## Warning #3 — `get_compare` doesn't route anchor through `_today()`

In `src/atlas20/api/services.py:206-212`, `get_compare()` calls
`get_settings()` directly, NOT `get_settings().model_copy(update={"anchor_date": _today()})`
like `get_overview()` at `services.py:48-51` does.

Then `compare.py:_effective_anchor` (line 149) reads
`settings.anchor_date or datetime.now(timezone.utc).date()` — bypassing the
`_today()` indirection.

The brief invariant: "NO `random`, NO `datetime.now()` outside `_today()`".

**Fix two ways simultaneously:**
1. In `services.py:get_compare`, mirror the `get_overview` pattern:
   `settings = get_settings().model_copy(update={"anchor_date": _today()})`
2. In `compare.py:_effective_anchor`, remove the `datetime.now(timezone.utc)`
   fallback — when `settings.anchor_date is None`, raise ValueError instead
   (defensive — should never happen if service layer wires it correctly).
3. Add `from datetime import` cleanup: remove unused `datetime`, `timezone`
   imports from `compare.py` if no longer used.

## Procedure

1. Fix each warning in a SEPARATE commit:
   - `fix(api): batch 5 reviewer pass — reject NaN/inf in compare/options validators`
   - `refactor(api): batch 5 reviewer pass — extract data_access/_common.py helpers`
   - `fix(api): batch 5 reviewer pass — route compare anchor through _today()`

2. After EACH commit, run `python -m pytest tests/ -x -q` and confirm green.

3. Run `cd apps/web && npm run typecheck` after the refactor commit to make
   sure no frontend break.

4. Final report:
   - Three commit hashes
   - Final test count (should still be 109+ if you added the NaN regression test)
   - Any deviations
