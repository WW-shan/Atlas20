# Retro-Cleanup — Batches 1-5 Info/Warning sweep

Per new protocol (commit `48afe0e`): all findings including Info get fixed.
Opus 4.7 retro audit surfaced 8 actionable items. Each is a separate commit.

## Order of fixes (each = its own commit)

### 1. B5-1 [Warning] — Drop redundant `to_numeric` pre-passes

**Files:**
- `src/atlas20/api/data_access/compare.py:71-74` (in `_load_compare_summary`)
- `src/atlas20/api/data_access/compare.py:232-234` (in `_load_latest_universe`)
- `src/atlas20/api/data_access/options.py:52-54` (in `load_options_from_reports`)

**Current pattern (redundant):**
```python
parsed[column] = pd.to_numeric(parsed[column], errors="raise")
parsed[column] = parsed[column].map(_as_float)
```

`pd.to_numeric(errors="raise")` only raises on non-coercible strings; it allows NaN. Then `_as_float.map` is what actually rejects NaN/inf. The two-step is wasted work.

**Fix:** keep only the `_as_float.map` step. Wrap in `try/except (TypeError, ValueError)` for clear error message:
```python
try:
    parsed[column] = parsed[column].map(_as_float)
except ValueError as exc:
    raise ValueError(f"{path} has invalid numeric values in {column}") from exc
```

**Commit message:** `refactor(api): retro — drop redundant to_numeric in NaN-guarded loaders`

---

### 2. B4-1 [Warning] — Consolidate `_as_*` helpers

**Problem:** `universe.py:201-242` has locally-defined `_as_symbol`, `_as_text(value, *, default)`, `_as_bool`, `_as_date`, `_as_float(value, column)`. `_common.py:62-78` has different signatures: `_as_text(value, column)` and `_as_float(value)` (no column).

Name collision risk: someone does `from .._common import _as_text` in universe.py and gets the wrong signature.

**Fix decisions (Claude):**

a) Promote the column-aware variant as canonical in `_common.py`:
   - `_as_float(value, column: str | None = None) -> float` — column optional for backward compat with existing call sites that don't pass it (compare.py, options.py). If column is None, error message says "non-finite numeric value".
   - `_as_text(value, column: str) -> str` — already correct in `_common.py`, no change.

b) In `universe.py`, rename divergent helpers:
   - `_as_text(value, *, default)` → `_as_text_or_default(value, *, default)` — distinct name, distinct semantics (allows missing value, returns default).
   - `_as_symbol` → keep, but make it a thin wrapper: `def _as_symbol(value, column): return _as_text(value, column)`.
   - `_as_bool` and `_as_date` — these are universe-specific. Keep local but document why.
   - `_as_float(value, column)` — REMOVE local copy; import from `_common.py` (now compatible after step a).

c) Update all call sites in `universe.py` to use renamed `_as_text_or_default`.

**Tests:** existing tests should still pass. Add one test asserting `_common._as_float(float('nan'), 'foo')` raises ValueError with column name in message.

**Commit message:** `refactor(api): retro — consolidate _as_* helpers, rename universe _as_text_or_default`

---

### 3. B1-1 [Warning] — `_latest_report_dir` honors `latest.txt`

**File:** `src/atlas20/api/data_access/_common.py:11-15`

**Current:**
```python
def _latest_report_dir(report_root: Path) -> Path:
    latest = report_root / "latest"
    return latest if latest.exists() else report_root
```

**Fix:** read pointer file first.

```python
def _latest_report_dir(report_root: Path) -> Path:
    pointer = report_root / "latest.txt"
    if pointer.exists():
        try:
            target_name = pointer.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"Could not read {pointer}: {exc}") from exc
        if target_name:
            target = report_root / target_name
            if target.exists():
                return target
    fallback = report_root / "latest"
    return fallback if fallback.exists() else report_root
```

**Test:** add `tests/test_latest_pointer.py`:
- given tmp report_root with `latest.txt` pointing to `run_001/` and `run_001/strategy_summary.csv` exists, assert `_latest_report_dir` returns `run_001` path.
- given malformed `latest.txt` (whitespace only), assert falls back to `latest/` dir.
- given missing pointer, assert falls back to `latest/` dir.

**Commit message:** `feat(api): retro — _latest_report_dir honors reports/latest.txt pointer`

---

### 4. B2-1 + B2-2 [Info] — Centralize `_today()` and UTC-ISO formatters

**Decision:** create `src/atlas20/api/_time.py` (NOT `_common.py` — that's data_access-scoped).

Contents:
```python
"""Project-wide time helpers — only place that calls datetime.now()."""

from datetime import date, datetime, timezone
from pathlib import Path

from atlas20.api.settings import get_settings


def today() -> date:
    settings = get_settings()
    if settings.anchor_date is not None:
        return settings.anchor_date
    return datetime.now(timezone.utc).date()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_iso_from_timestamp(ts: float) -> str:
    return (
        datetime.fromtimestamp(ts, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def utc_iso_from_path_mtime(path: Path) -> str:
    return utc_iso_from_timestamp(path.stat().st_mtime)
```

**Migrations:**
- `src/atlas20/api/services.py`: replace local `_today()` with `from atlas20.api._time import today`. Use `today()` everywhere. Replace inline `datetime.now(...).isoformat(...)` calls (lines ~269 and ~307-310) with `utc_now_iso()` / `utc_iso_from_path_mtime()`.
- `src/atlas20/api/data_access/overview.py:34`: replace `settings.anchor_date or datetime.now(timezone.utc).date()` with `today()`.
- `src/atlas20/api/data_access/compare.py:_effective_anchor`: already routed through settings.anchor_date — verify no `datetime.now()` left; clean up `from datetime import` if `datetime` no longer used.
- `src/atlas20/reporting/report.py:96-101`: refactor `_mtime_iso` to use `utc_iso_from_path_mtime`.

**Tests:** existing tests still pass. Add `tests/test_time_helpers.py` covering:
- `today()` honors `settings.anchor_date`
- `today()` falls back to UTC date when anchor None (monkeypatch datetime as in existing test)
- `utc_now_iso()` returns ISO with `Z` suffix
- `utc_iso_from_timestamp(0)` returns `"1970-01-01T00:00:00Z"`

**Commit message:** `refactor(api): retro — extract _time module; single datetime.now() entry`

---

### 5. B5-4 [Info] — Extract test CSV fixtures to conftest.py

**Files affected (5):**
- `tests/test_compare_data_access.py`
- `tests/test_universe_data_access.py`
- `tests/test_options.py`
- `tests/test_services_overview_fallback.py` (if exists; else skip)
- `tests/test_featured_digest.py`

**Move to `tests/conftest.py`:**
- Constants: `SUMMARY_HEADER`, `EQUITY_HEADER`, `DAILY_RETURNS_HEADER`, `REBALANCE_HEADER`, `DATA_QUALITY_HEADER`
- Helpers:
  - `write_summary_csv(report_root, rows)`
  - `write_equity_csv(report_root, rows)`
  - `write_daily_returns_csv(report_root, rows)`
  - `write_rebalance_csv(data_root, rows)`
  - `write_data_quality_csv(data_root, rows)`
  - `make_summary_row(strategy, **overrides)` — keyword-overrides for sharpe/cagr/etc
  - `make_rebalance_row(symbol, rebalance_date, rank, **overrides)`

**Each test file** then imports these helpers (NOT through `from conftest` — conftest is auto-discovered). Place them as top-level functions OR as a `pytest.fixture(scope="session")` that returns a builder object. **Use plain top-level functions** — explicit imports break under pytest discovery if conftest functions are imported directly. Instead, expose via a `pytest.fixture` named `csv_writer` that yields a small dataclass `CsvWriter` with the methods.

Actually, simpler: just put plain function definitions in conftest.py and tests import them: `from tests.conftest import write_summary_csv`. This works because `tests/` is a package if `tests/__init__.py` exists; check first.

**Check first:** `ls tests/__init__.py`. If absent, add empty `__init__.py`. If present, just use `from tests.conftest import ...`.

**Reduce duplicate constants:** `REBALANCE_HEADER` is defined verbatim in compare/universe/options test files. After this refactor, each file should have at most ~5 lines of header/row construction, all delegating to conftest.

**Net impact:** Currently ~150 LOC of duplicated fixture code → ~50 LOC in conftest + ~5-10 LOC per consumer = roughly -100 net. Existing tests must still pass with zero behavior change.

**Commit message:** `refactor(tests): retro — extract CSV-building fixtures into conftest`

---

### 6. B3-2 [Info] — Align featured-digest separator

**File:** `src/atlas20/api/services.py:285-294`

**Current:** `f"{overview['champion']['strategy']} - YTD {ytd_pct:+,.2f}% - generated {generated_at}"`

**Fix:** match mock_data's middle-dot separator:
```python
f"{overview['champion']['strategy']} · YTD {ytd_pct:+,.2f}% · generated {generated_at}"
```

**Test:** verify `tests/test_featured_digest.py` covers this — the subtitle should contain `·`. Update the assertion if it currently expects `-`.

**Commit message:** `fix(api): retro — align featured digest subtitle separator to middle dot`

---

### 7. B5-2 [Info] — Mock `fallback_universe_timeline.tokens` shape alignment

**File:** `src/atlas20/api/mock_data.py:448-478`

**Current:** `tokens` reuses `universe_tickers` (alphabetic? frequency-ordered? unclear).

**Decision:** the real adapter orders by frequency DESC then symbol ASC. Reorder mock tokens to match a plausible frequency-ranked output (BTC, ETH, BNB, XRP, SOL, ADA, DOGE, ... — by approximate market cap rank).

Also ensure `tokens` length is exactly 20 (matches the cap).

**Test:** if `tests/test_api_routes.py` snapshot-tests universe timeline, update the assertion. Otherwise no test change.

**Commit message:** `fix(api): retro — align fallback universe tokens with real-adapter ranking`

---

## Procedure

7 commits, in the order above. After each:
- `python -m pytest tests/ -x -q` green
- After commit #5: also `cd apps/web && npm run typecheck` (no impact expected, but verify)

## Final verification

- `pytest tests/` count: should land at 113 + ~5 new = ~118
- All 7 commits stage cleanly
- No file outside `src/atlas20/api/`, `src/atlas20/reporting/`, `tests/` modified
- `.ccg/tasks/review-r3-premium-redesign/.turns.json` left untouched

## Report

For each of the 7 commits:
- Hash
- Files changed (count)
- Test count delta

Final summary: net LOC delta, total tests count, any items that turned out
to be inapplicable (and why).

Each commit must be ATOMIC — do not bundle. The order above respects
dependencies (B5-1 doesn't depend on others; B4-1 must come before B5-1
since B5-1 leans on the new `_as_float` signature; B1-1 standalone;
B2-1/B2-2 affect _today() use sites which B4-1 also touches — finish B4-1
first, then B2 cleanup).

Adjust the order if you find a dependency conflict, but report the change.
