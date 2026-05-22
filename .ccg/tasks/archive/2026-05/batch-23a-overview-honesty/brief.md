# Batch 23a — Overview UX Honesty + Chart Empty State

## Goal

Eliminate UI lies on the Overview tab by sourcing all display labels, cadences, and freshness signals from real backend payload fields. Plus give the equity chart an honest empty-state instead of a silent blank SVG.

Addresses CHANGELOG `[Unreleased]` B23 candidates + first-pass + cross-validation findings: **C1, C2, C3, W1, W2, W3, N1-blank-chart, N6-test-locks-C1**.

## Scope

PR size: ~150 LOC (backend ~50, frontend ~70, tests ~30). Single tab. Backend schema additions to `ChampionSummary` + `OverviewPayload` only.

## Inputs/Outputs

**Backend (read):**
- `src/atlas20/api/data_access/overview.py` — `_build_champion`, `_build_equity_overlay`, `_build_rebalance`
- `src/atlas20/api/schemas.py` — `ChampionSummary`, `OverviewPayload`, `EquityOverlay`, `RebalanceInfo`
- `reports/latest.txt` + `reports/<dir>/` mtime for `last_sync_seconds`

**Backend (write):**
- `schemas.py`: add `ChampionSummary.display_name: str` (required, derived). Add `OverviewPayload.last_sync_seconds: int`. Add `EquityOverlay.atlas_label: str`, `EquityOverlay.btc_label: str`. Populate existing `ChampionSummary.rebalance_frequency: str | None` (was always `None`).
- `data_access/overview.py`: new `_format_display_name(strategy: str) -> str`, new `_parse_cadence(strategy: str, selection_history: pd.DataFrame | None) -> str | None`, new `_compute_last_sync_seconds(report_root: Path) -> int`. Adjust `_build_champion`, `_build_equity_overlay` to populate new fields. Adjust `_build_equity_overlay` to fall back to "ALL" range when YTD slice is empty AND the underlying series has data outside YTD.
- `tests/test_overview_data_access.py`: new regression tests for the 4 new behaviors.

**Frontend (write):**
- `apps/web/src/lib/api.ts`: extend `ChampionSummary`, `OverviewPayload`, `EquityOverlay` types to match new schema. Update `fallbackOverview` to populate new fields with reasonable values (real-looking strategy slug + display_name).
- `apps/web/src/features/overview/OverviewTab.tsx`:
  - Hero `<h2>` (line 74-76): render `champion.display_name`, not `champion.strategy`.
  - Equity overlay (lines 157-177): drop the tablist entirely (role="tab", buttons); update the SectionHeader copy from `EQUITY CURVE · YTD` to `EQUITY CURVE · {equity_overlay.range}`. Use `equity_overlay.atlas_label` and `equity_overlay.btc_label` for `<OverlayLineChart lines>` AND the legend chips below.
  - Rebalance subtitle (line 184): render `champion.rebalance_frequency ?? "—"` instead of hardcoded "weekly".
  - Action strip (lines 233-237): replace hardcoded "Last sync: 18s ago" with `formatRelativeAge(overview.last_sync_seconds)` returning "{n}s ago" / "{n}m ago" / "{n}h ago".
- `apps/web/src/components/charts/OverlayLineChart.tsx`: when `series.length === 0`, render a centered `<text>` element "No data in selected range" inside the SVG (foreignObject ok if styling). Match existing text color tokens.
- `apps/web/src/features/overview/OverviewTab.test.tsx`: update the C1 assertion (line 12) to use `fallbackOverview.equity_overlay.atlas_label`. Add tests for: rebalance cadence rendering, display name in hero, last-sync formatting, equity chart empty-state copy.

## Algorithm — key decisions

### `_format_display_name(strategy)`

Use the existing `_strategy_family` lookup table plus a variant suffix:
```python
def _format_display_name(strategy: str) -> str:
    family = _strategy_family(strategy)  # already exists at overview.py:227
    # Strip the family prefix and convert what's left.
    for prefix, _ in _STRATEGY_FAMILY_PREFIXES:
        if strategy.startswith(prefix):
            variant = strategy[len(prefix):].lstrip("_")
            if not variant:
                return family
            # "top8_biweekly__bull_only" → "Top-8 Biweekly · Bull Only"
            cleaned = variant.replace("__", " · ").replace("_", " ")
            return f"{family} · {cleaned.title()}"
    return strategy  # unknown prefix → raw slug as last resort
```

Examples (use these as test cases):
- `TOP20_MOM_top8_biweekly__bull_only` → `"Momentum Rotation · Top8 Biweekly · Bull Only"`
- `TOP20_SECTOR_top3_biweekly__bull_only` → `"Sector Rotation · Top3 Biweekly · Bull Only"`
- `BTC_BH__always_on` → `"BTC Benchmark · Always On"`
- `MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK` → `"Momentum Lead Top1 All 14d Stop11 Confirm2 Btc Park"` (no family prefix matches; we get the raw slug as last resort — that's acceptable)

### `_parse_cadence(strategy, selection_history)`

1. Slug match first (deterministic):
   ```python
   for token, label in [("_weekly_", "Weekly"), ("_biweekly_", "Biweekly"),
                         ("_monthly_", "Monthly"), ("_14d_", "Biweekly"),
                         ("_7d_", "Weekly"), ("_30d_", "Monthly")]:
       if token in strategy.lower():
           return label
   ```
2. Fall back to selection_history median diff between unique rebalance_dates for this strategy:
   - ≤8d → "Weekly", 9-21d → "Biweekly", 22-45d → "Monthly", else → `f"{median_days}D"`
3. If neither works → `None`.

### `_compute_last_sync_seconds(report_root)`

```python
def _compute_last_sync_seconds(report_root: Path) -> int:
    latest_txt = report_root / "latest.txt"
    if latest_txt.exists():
        target = (report_root / latest_txt.read_text().strip()).resolve()
        if target.exists():
            return max(0, int(time.time() - target.stat().st_mtime))
    # Fallback: mtime of latest_report_dir itself
    try:
        return max(0, int(time.time() - _latest_report_dir(report_root).stat().st_mtime))
    except (FileNotFoundError, ValueError):
        return 0
```

Returns seconds since the report's mtime. 0 if unknown.

### `_build_equity_overlay` — YTD fallback to ALL

Current behavior: when YTD slice is empty, returns `{"series": [], "range": "YTD"}`. Change:

```python
def _build_equity_overlay(equity_curves_df, champion_col, anchor_date):
    # ... existing setup with concat + dropna ...
    if series.empty:
        raise ValueError("equity_curves.csv has no overlapping atlas+btc data")
    start = pd.Timestamp(date(anchor_date.year, 1, 1))
    end = pd.Timestamp(anchor_date)
    ytd = series[(series.index >= start) & (series.index <= end)]
    if ytd.empty:
        ytd = series  # fall back to full available range
        range_label = "ALL"
    else:
        range_label = "YTD"
    base = ytd.iloc[0]
    # ... existing base validation + resample/iter ...
    return {
        "series": points,
        "range": range_label,
        "atlas_label": _format_display_name(champion_col),
        "btc_label": "BTC Benchmark",
    }
```

### Frontend `formatRelativeAge(seconds)`

```ts
function formatRelativeAge(s: number): string {
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
```

Place in `OverviewTab.tsx` near the existing `formatPct` helpers.

### `OverlayLineChart` empty-state

Inside the existing SVG, when `series.length === 0`:
```tsx
<text
  x="50%" y="50%"
  textAnchor="middle"
  dominantBaseline="middle"
  fontSize={12}
  fill="var(--muted)"
  className="mono"
>
  No data in selected range
</text>
```
Don't render lines / axes when empty. Aria-label stays for screen readers.

## Tests (must cover)

1. `_format_display_name` produces stable strings for the 4 examples above.
2. `_parse_cadence` slug match returns "Biweekly" for `TOP20_MOM_top8_biweekly__bull_only`.
3. `_parse_cadence` falls back to selection_history median when slug has no cadence token; assert "Biweekly" for a synthetic history with 14-day gaps.
4. `_parse_cadence` returns `None` when both paths fail.
5. `_compute_last_sync_seconds` returns nonzero when `latest.txt` points at an existing dir; returns 0 cleanly when files are missing.
6. `_build_equity_overlay` falls back to range="ALL" and a non-empty series when YTD slice is empty but historical data exists.
7. `_build_equity_overlay` returns `atlas_label` matching `_format_display_name(champion_col)` and `btc_label == "BTC Benchmark"`.
8. Frontend `OverviewTab` renders `champion.display_name` in hero (use a fixture with `display_name = "Momentum Rotation · Top8 Biweekly"`).
9. Frontend renders `equity_overlay.atlas_label` in chart legend (NOT "ATLAS Adaptive v3").
10. Frontend renders rebalance cadence from `champion.rebalance_frequency` (NOT "weekly").
11. Frontend renders `formatRelativeAge(last_sync_seconds)` — assert "{n}s ago" / "m ago" / "h ago" boundaries (59/60/3599/3600).
12. Frontend `OverlayLineChart` renders the "No data in selected range" text when `series.length === 0`.
13. Frontend `OverviewTab.test.tsx:12` updated to use payload field, not the literal `"ATLAS Adaptive v3"`.

## Out of scope

- C4 (Tracked Notional sum-vs-sparkline) — deferred to B23b
- W4/W5/W6 (Compare cleanup) — deferred to B24
- N2-mock-leak (silent fallback discriminator) — deferred to B24 with UX decision needed
- N3-report-contract — deferred to B25
- N4-api-key-auth — deferred to B25
- I1/I2 (quick wins) — fold into B24 or post-B24

## Acceptance

- pytest count: was 368 → expect ≥ 374 (7 new backend tests for the 4 new helpers + edge cases)
- vitest count: was 163 → expect ≥ 168 (5 new frontend tests for new payload-driven renders + empty-state)
- `npm --prefix apps/web run typecheck` clean
- `npm --prefix apps/web run build` clean
- All CI jobs green
- Smoke: hit `/api/overview` and confirm new fields present (`champion.display_name`, `champion.rebalance_frequency`, `equity_overlay.atlas_label`, `equity_overlay.btc_label`, `overview.last_sync_seconds`)

## Files expected to change

| File | Δ LOC est | Reason |
|------|-----------|--------|
| `src/atlas20/api/schemas.py` | +5 | Add 3 fields |
| `src/atlas20/api/data_access/overview.py` | +50 | 3 new helpers + tweak `_build_champion`/`_build_equity_overlay` |
| `tests/test_overview_data_access.py` | +60 | 7 new regression tests |
| `apps/web/src/lib/api.ts` | +6 | Type extensions + fallback values |
| `apps/web/src/features/overview/OverviewTab.tsx` | +15 / -20 | Replace hardcoded literals; drop tablist; add formatRelativeAge |
| `apps/web/src/features/overview/OverviewTab.test.tsx` | +30 | 5 new tests + update line 12 assertion |
| `apps/web/src/components/charts/OverlayLineChart.tsx` | +10 | Empty-state text |

Total: ~150 LOC net add, ~20 LOC removed (decorative tablist).
