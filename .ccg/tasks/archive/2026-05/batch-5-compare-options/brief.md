# Batch 5 — R3 Compare (real data) + R9 Options endpoint

## Goal

Wire `get_compare(ids, range_)` and `get_options_payload()` in
`src/atlas20/api/services.py` to real artifacts in `settings.report_root` with
mock fallback (same pattern as Batches 3–4).

## Scope (PR-sized, ~300 LOC + ~150 LOC tests)

### R3 — Compare from `equity_curves.csv` + `strategy_summary.csv`

**Inputs:**
- `reports/latest/equity_curves.csv`: column 0 = date (named `Unnamed: 0`),
  columns 1..30 = strategy names with daily equity values (start at 100_000).
- `reports/latest/strategy_summary.csv`: 12 columns —
  `strategy, total_return, cagr, annualized_volatility, sharpe, sortino,
  max_drawdown, calmar, monthly_win_rate, annualized_turnover,
  avg_turnover_per_rebalance, average_holdings`.

**Algorithm:**
1. Resolve each input `run_id` against the strategy column set:
   - If `run_id` is an exact column name (e.g. `BTC_BH__always_on`), use it.
   - If `run_id` is one of three legacy aliases (`atlas`, `momentum`,
     `meanrev`), map to a deterministic canonical strategy chosen ONCE at
     module load (atlas → highest sharpe excluding BTC_BH/ETH_BH benchmarks;
     momentum → highest-cagr `TOP20_MOM_*` row; meanrev → highest-sharpe
     `TOP20_SECTOR_*` row). Keep aliases working so the existing frontend
     contract still resolves.
   - Unknown id → skip silently (do not raise).
2. If zero ids resolve → fall back to mock (existing behaviour).
3. **Range filter** (`range_`: `"1M" | "3M" | "YTD" | "1Y" | "ALL"`):
   - `ALL`: full equity_curves.csv.
   - `1M / 3M / 1Y`: last 30 / 90 / 365 calendar days from `_today()` anchor;
     if anchor is beyond data, use last available date as anchor.
   - `YTD`: from Jan-1 of anchor year through anchor.
4. Downsample equity series: cap at **180 points** (decimate evenly); always
   include first and last row. Compute downsampling AFTER range filter.
5. Normalize equity to base = 1.0 at the first point in the range so all
   strategies start at the same level for visual compare.
6. **Metrics**: pull rows from strategy_summary.csv for the resolved set.
   Map columns to `CompareMetrics` keys:
   - `cagr` ← `cagr`
   - `sharpe` ← `sharpe`
   - `sortino` ← `sortino`
   - `max_dd` ← `max_drawdown`
   - `calmar` ← `calmar`
   - `win_rate` ← `monthly_win_rate`
   - `avg_turnover` ← `annualized_turnover`
   - `trades_per_year` ← derive: `annualized_turnover` (already per-year,
     same numeric — repeat the value for now since strategy_summary doesn't
     have a separate trade-count column)

   Use Batch-3 `_as_float` to reject NaN/inf.
7. **Overlap matrix**: synthesize from rebalance_universe.csv at the latest
   rebalance date — take the universe symbols and compute pairwise Jaccard
   approximations across strategies based on the strategy-name conventions:
   - `TOP20_*` strategies share the full top-20 universe → high overlap.
   - `BTC_BH` / `ETH_BH` → single asset, overlap with any TOP20 = 1/20.
   - Identical strategies → 1.0 on diagonal.

   This is heuristic but deterministic; keep a comment explaining the proxy.
   `sharedHoldings` = top-3 symbols by universe_rank at latest rebalance,
   each `{symbol, count=N_strategies_holding_it, total=len(present_ids)}`.

**Service-layer integration:**

```python
def get_compare(ids: list[str], range_: str) -> ComparePayload:
    settings = get_settings()
    try:
        payload = load_compare_from_reports(settings, ids, range_)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock compare: %s", exc)
        # preserve existing mock-subset logic (already present below)
        return _get_compare_mock(ids, range_)
    return ComparePayload.model_validate(payload)
```

Refactor the existing `get_compare` body into a private `_get_compare_mock`
helper so the fallback path stays semantically identical to today's
behaviour.

### R9 — Options endpoint

Replace `get_options_payload() -> dict[str, Any]` (currently returns `{}`)
with a typed payload sourced from real data.

**New schema** in `src/atlas20/api/schemas.py`:

```python
class OptionsUniverseSize(ApiModel):
    topN: int
    label: str

class OptionsRebalance(ApiModel):
    value: Literal["Weekly", "Biweekly", "Monthly"]
    label: str

class OptionsPayload(ApiModel):
    presets: list[str]               # strategy names from strategy_summary.csv
    universes: list[OptionsUniverseSize]  # [{topN: 5/10/20, label: "Top 5"}, ...]
    rebalances: list[OptionsRebalance]
    feeBpsRange: list[float]         # [min, default, max] -> [0.0, 10.0, 50.0]
    slippageBpsRange: list[float]    # [0.0, 5.0, 25.0]
    sectors: list[str]               # unique sector values from rebalance_universe
```

**Algorithm:**
- `presets`: `strategy_summary.csv['strategy']` sorted by sharpe DESC, cap 30.
- `universes`: hard-coded `[5, 10, 20]` with labels.
- `rebalances`: hard-coded 3-entry list matching `BacktestWindow` literal.
- `sectors`: `rebalance_universe.csv['sector'].drop_duplicates().sort()` at
  latest rebalance date.
- `feeBpsRange` / `slippageBpsRange`: constants.

Fall back to a frozen `mock_data.fallback_options` dict (NEW — add it) when
real files are missing.

**Service:**

```python
def get_options_payload() -> OptionsPayload:
    settings = get_settings()
    try:
        payload = load_options_from_reports(settings)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock options: %s", exc)
        payload = deepcopy(mock_data.fallback_options)
    return OptionsPayload.model_validate(payload)
```

Update the existing options route handler to return `OptionsPayload` (it
currently returns `dict[str, Any]`).

### U6 frontend wire

The frontend already has `getOptions()` in `apps/web/src/lib/api.ts:529`.
Check whether any feature consumes it. If `BacktestStudioTab` or
`StrategyCompareTab` could benefit from real presets/sectors, add a
TanStack query with `initialData` fallback. Keep the change small — if no
consumer exists yet, just type the response (`OptionsPayload` interface) on
the frontend side and leave wiring for later.

**Out of scope:** redesigning the Compare or Builder UIs.

## Tests (new file `tests/test_compare_data_access.py` + extend `tests/test_options.py`)

1. `test_load_compare_filters_by_run_ids` — synthetic equity_curves + summary
   with 3 strategies; pass 2 ids; assert payload only contains those 2.
2. `test_load_compare_resolves_legacy_aliases` — pass `["atlas", "momentum",
   "meanrev"]`; assert all three resolve to real strategy names.
3. `test_load_compare_unknown_id_skipped` — pass `["BTC_BH__always_on",
   "NO_SUCH_STRATEGY"]`; assert only the known one in result.
4. `test_load_compare_all_unknown_raises_valueerror` — pass `["x", "y"]`;
   assert raises ValueError (so service falls back to mock).
5. `test_load_compare_range_filter` — anchor=2026-05-19, range="1M"; assert
   first equity point >= 2026-04-19.
6. `test_load_compare_caps_at_180_points` — long equity range; assert <=180
   points + first/last preserved.
7. `test_load_compare_normalizes_to_base_one` — assert first point value == 1.0
   for every strategy.
8. `test_load_compare_metrics_from_summary` — assert metric values match CSV.
9. `test_load_options_payload_from_real_data` — synthetic
   strategy_summary + rebalance_universe; assert presets sorted by sharpe,
   sectors deduplicated, feeBpsRange constants present.
10. `test_load_options_falls_back_on_missing_data` (in
    `test_api_services.py`) — empty report_root → mock fallback.
11. `test_get_compare_falls_back_when_reports_missing` — same pattern.

All tests use `tmp_path` synthetic CSVs and `Settings(report_root=tmp,
data_root=tmp)`. Use `atlas20_test_env` autouse fixture for anchor date.

## Files expected to change

- `src/atlas20/api/data_access/compare.py` — NEW (~200 LOC)
- `src/atlas20/api/data_access/options.py` — NEW (~80 LOC)
- `src/atlas20/api/schemas.py` — add `OptionsPayload` + sub-models (~30 LOC)
- `src/atlas20/api/services.py` — wire compare + options, add
  `_get_compare_mock` (~50 LOC delta)
- `src/atlas20/api/mock_data.py` — add `fallback_options` (~25 LOC delta)
- `src/atlas20/api/routes/options.py` — change return type to OptionsPayload
- `tests/test_compare_data_access.py` — NEW (~200 LOC)
- `tests/test_options.py` — extend or NEW (~80 LOC)
- `tests/test_api_services.py` — +2 fallback tests
- `apps/web/src/lib/api.ts` — type `getOptions` return as `OptionsPayload`
  (~10 LOC delta; do NOT add new query hook unless trivial)

## Out of scope

- Worker queue (Batch 9).
- DB persistence (Batch 7).
- Replacing mock for `register_new_backtest` / `list_runs_queue`.
- BuilderTab UI changes.
- Real per-run equity overlays for Run Detail (Batch 10).

## Acceptance

- `pytest tests/` all green (98 → ~109).
- Backend boots: `uvicorn atlas20.api.app:app` — `/compare?ids=BTC_BH__always_on,ETH_BH__always_on&range=1Y`
  returns 200 with real shape. `/options` returns 200 with `presets` ≥ 10.
- No Critical findings from codex reviewer.
- Frontend type-check: `cd apps/web && npm run typecheck` clean.

## Implementation notes

- Reuse `_as_float`, `_as_text`, `_read_processed_csv` helpers from
  `data_access/overview.py` and `data_access/universe.py` — extract to
  `data_access/_common.py` if used in 3+ modules.
- All raised errors must be `FileNotFoundError` or `ValueError` so the
  service-layer try/except can catch and fall back to mock.
- Determinism: NO `random`, NO `datetime.now()` outside `_today()`.
