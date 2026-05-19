# Batch 4 — R6 Universe Timeline + R8 Data Alerts (real CSV-backed)

## Goal

Replace mock-only `get_universe_timeline()` and `get_data_alerts()` in
`src/atlas20/api/services.py` with adapters that read real artifacts from
`settings.data_root / "processed"`, falling back to existing mock data when
files are missing or malformed (same pattern as Batch 3 R1/R5).

Frontend `UniverseHealthTab.tsx` already consumes these endpoints through
TanStack Query with `initialData=fallback…` — do **not** rewrite the frontend
in this batch unless tests break.

## Scope (PR-sized, ~250 LOC + tests)

### R6 — Universe Timeline from `rebalance_universe.csv`

**Input file:** `data/processed/rebalance_universe.csv` (2781 rows, 190 unique
rebalance_dates, 2021-03-31 → 2026-04-21).

Columns: `coin_id, price, market_cap, volume_usd, history_days, symbol, name,
sector, rebalance_date, universe_rank`.

**Output schema** (must validate as `UniverseTimelinePayload`):

```python
{
  "tokens": list[str],        # union of symbols in window, capped at 20
  "segments": list[{"token": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}],
  "rotations": list[{"ts": "YYYY-MM-DD", "label": str}],
  "range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
}
```

**Algorithm:**
1. Read CSV, parse `rebalance_date` as datetime, sort.
2. **Window**: take the most recent 180 calendar days ending at the latest
   rebalance_date (NOT `_today()` — anchor to real data, since the latest date
   may lag today).
3. **Tokens**: collect the set of `symbol` values whose `universe_rank ≤ 20`
   anywhere in the window. Order by *frequency of appearance* (most frequent
   first); cap at 20.
4. **Segments**: for each of those 20 tokens, build contiguous date ranges
   where it appeared (universe_rank ≤ 20). A "gap" of one missing rebalance
   date splits a segment. `start` = first appearance in the segment,
   `end` = last appearance.
5. **Rotations**: detect rebalance dates where the top-20 set differs from
   the previous rebalance by ≥ 3 symbols (Jaccard distance proxy). Label each
   as `"MAJOR ROTATION"`. Cap at 6 most recent.
6. **range**: `{start: first_date_in_window, end: latest_rebalance_date}`.

**Numeric guards:** reuse Batch 3 `_as_float` pattern if numeric extraction is
needed (none here — all string output).

### R8 — Data Alerts from `data_quality.csv`

**Input file:** `data/processed/data_quality.csv` (58 rows, 17 cols).

Relevant columns: `symbol, validation_passed, validation_reason,
latest_overlap_date, latest_price_gap, median_price_gap, price_correlation,
included_in_panel`.

**Output schema** (validates as `list[DataAlert]`):

```python
{
  "id": "dq_{symbol_lower}",
  "severity": "rose" | "cyan" | "emerald",
  "title": str,
  "meta": str,
  "ts": "YYYY-MM-DDTHH:MM:SSZ",
  "icon": "alert-triangle" | "info" | "check-circle",
}
```

**Rules:**
- If `validation_passed=False` → `severity="rose"`, `icon="alert-triangle"`,
  title `f"{symbol} · {validation_reason} — review required"`.
- Else if `price_correlation < 0.98` → `severity="cyan"`, `icon="info"`,
  title `f"{symbol} · price correlation {price_correlation:.3f} below 0.98"`.
- Else if `latest_price_gap > 0.005` → `severity="cyan"`, `icon="info"`,
  title `f"{symbol} · latest price gap {latest_price_gap:.2%}"`.
- Else if row would emit nothing → skip (do NOT add emerald "all healthy"
  rows; an empty list is acceptable).
- `meta`: include latest_overlap_date and panel-inclusion status.
- `ts`: derive from `latest_overlap_date` (append `T00:00:00Z`).
- Sort by severity rank (rose > cyan > emerald) then by symbol asc.
- Cap at 12 rows; if more would exist, drop the lowest-priority overflow.

If `validation_passed=True` for ALL rows AND no thresholds tripped → return
an empty list `[]` (frontend already handles 0-alert case via "OPEN: 0" pill).

### Service-layer integration

In `src/atlas20/api/services.py`:

```python
def get_universe_timeline() -> UniverseTimelinePayload:
    settings = get_settings()
    try:
        payload = load_universe_timeline_from_processed(settings)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock universe timeline: %s", exc)
        payload = deepcopy(mock_data.fallback_universe_timeline)
    return UniverseTimelinePayload.model_validate(payload)


def get_data_alerts() -> list[DataAlert]:
    settings = get_settings()
    try:
        rows = load_data_alerts_from_processed(settings)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock data alerts: %s", exc)
        rows = deepcopy(mock_data.fallback_data_alerts)
    return [DataAlert.model_validate(row) for row in rows]
```

**`data_sources` stays mock-only** in this batch (no real source-health
telemetry yet — that's Batch 13 / O3).

### New file: `src/atlas20/api/data_access/universe.py`

Implements `load_universe_timeline_from_processed(settings: Settings) -> dict`
and `load_data_alerts_from_processed(settings: Settings) -> list[dict]`.

Use `pd.read_csv` with the same `EmptyDataError`/`ParserError` handling as
`overview.py`. Raise `FileNotFoundError` or `ValueError` for any contract
violation; the service layer catches both and falls back.

### Tests — new file `tests/test_universe_data_access.py`

Cover at minimum:

1. `test_load_universe_timeline_builds_segments_from_real_data` — point
   `settings.data_root` at a tmpdir containing a synthetic CSV with 3 tokens
   over 4 rebalance dates; assert tokens, segments[0].start/end, range.
2. `test_load_universe_timeline_window_is_180d_from_latest` — synthesize CSV
   with one row 200 days before latest; assert it's excluded.
3. `test_load_universe_timeline_detects_major_rotation` — synthesize CSV
   where 4 tokens swap between two consecutive dates; assert one rotation
   entry produced.
4. `test_load_universe_timeline_caps_tokens_at_20` — 25 tokens active; only
   top 20 by frequency appear.
5. `test_load_universe_timeline_missing_csv_raises_filenotfound` — verify
   service-layer fallback path is exercised.
6. `test_load_data_alerts_emits_validation_failures_first` — synthesize CSV
   with one rose + one cyan; assert order and `id` format.
7. `test_load_data_alerts_returns_empty_for_clean_data` — all validations
   pass and thresholds within bounds → empty list.
8. `test_load_data_alerts_caps_at_12` — synthesize 15 failing rows; assert
   only 12 returned.
9. `test_get_universe_timeline_falls_back_on_missing_data` (in
   `test_api_services.py`) — point settings.data_root at empty tmpdir, assert
   payload equals `mock_data.fallback_universe_timeline`.
10. `test_get_data_alerts_falls_back_on_missing_data` — same pattern.

Use the existing `atlas20_test_env` autouse fixture from `tests/conftest.py`
to ensure deterministic anchor date. Tests must run < 1s each.

### Settings

`Settings.data_root` already exists (Batch 2). No new env vars.

## Out of scope

- DO NOT modify `get_data_sources` — source health is Batch 13.
- DO NOT modify `refresh_universe` — that returns just `refreshed_at`; real
  refresh is Batch 9 (worker queue).
- DO NOT touch frontend; query wires are already correct.
- DO NOT add new mock_data fields. Existing fallbacks stay verbatim.

## Acceptance

- `pytest tests/` all green (was 88 passing after Batch 3; expect ~98 after).
- `mypy src/` / `ruff check src/` clean (project may not have either; skip if
  no config exists).
- Backend boots cleanly: `uvicorn atlas20.api.app:app --port 8000` — hit
  `/universe/timeline` and `/data/alerts`, both return 200 with real-data
  shape (or fallback shape if data is missing).
- Codex reviewer pass with no Critical findings.

## Files expected to change

- `src/atlas20/api/data_access/universe.py` — NEW (~140 LOC)
- `src/atlas20/api/services.py` — modify `get_universe_timeline` + `get_data_alerts` (~30 LOC delta)
- `tests/test_universe_data_access.py` — NEW (~200 LOC)
- `tests/test_api_services.py` — add 2 fallback tests (~30 LOC delta)
