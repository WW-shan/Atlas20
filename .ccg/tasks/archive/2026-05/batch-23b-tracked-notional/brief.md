# Batch 23b — Tracked Notional Reality

## Goal

Fix the last known B23 UI lie: the Overview "Tracked Notional" card shows a headline dollar figure that sums across ALL strategies' final equity values, but the sparkline below it plots only the champion strategy's last 14 samples. Two different data sources juxtaposed without visual separation.

## Scope

PR size: ~40 LOC. Narrow. Single card in Overview tab. Backend data access only.

## Problem statement

`overview.py:_build_aum` computes:
- `current`: sum of ALL strategies' final equity values
- `sparkline`: champion equity last 14 samples
- `deltaPct`: champion's relative move across those 14 samples

The UI card title says "TRACKED NOTIONAL · RESEARCH" with a subtitle "{deltaPct} champion over 14 samples". A quick read assumes the $ figure, sparkline, and delta % are from the same source. They aren't.

## Algorithm

**Claude's decision:** Replace the headline with champion-only figures so all three values (headline, sparkline, delta%) come from the same source. The sum across strategies was never meaningful (each strategy starts from `initial_capital` independently — the sum isn't a real portfolio value).

### Change to `_build_aum`

```python
def _build_aum(
    summary_df: pd.DataFrame,
    equity_curves_df: pd.DataFrame,
    champion_equity: pd.Series,
) -> dict[str, Any]:
    if champion_equity.empty:
        return {"current": 0.0, "deltaPct": 0.0, "sparkline": []}
    spark_window = champion_equity.iloc[-14:]
    sparkline = [float(v) for v in spark_window.tolist()]
    current = float(spark_window.iloc[-1])
    if len(sparkline) >= 2:
        first = sparkline[0] or 1.0
        delta_pct = (sparkline[-1] - first) / first
    else:
        delta_pct = 0.0
    return {
        "current": current,
        "deltaPct": delta_pct,
        "sparkline": sparkline,
    }
```

Key change: `current` is now `champion_equity.iloc[-1]` (or equivalently `spark_window.iloc[-1]`), NOT the sum across all strategies. `sparkline` and `deltaPct` remain champion-only (unchanged). The `summary_df` and `equity_curves_df` parameters become unused — keep them in the signature to avoid breaking the call site in `load_overview_from_reports`.

### Frontend change

`OverviewTab.tsx` line 100: change the subtitle from `"{deltaPct} champion over 14 samples"` to `"{deltaPct} over last 14 data points"` — no longer needs the word "champion" since everything is from the same source.

### Schema change

None. `Aum` schema (`current: float, deltaPct: float, sparkline: list[float]`) stays the same. The semantic meaning of `current` changes (champion-only vs sum), but the shape doesn't.

## Tests (must cover)

1. `_build_aum` returns `current` equal to champion's last equity value (not the sum).
2. `_build_aum` returns the same sparkline as before (champion last 14).
3. `_build_aum` returns `deltaPct` matching the sparkline's relative move.
4. `_build_aum` returns `{current: 0.0, deltaPct: 0.0, sparkline: []}` when champion equity is empty.
5. Frontend subtitle text changes from "champion over 14 samples" to "over last 14 data points" (or similar wording that drops "champion").

## Out of scope

- Moving the sum to a separate card (could be a future B25 item)
- Changing the card title "TRACKED NOTIONAL · RESEARCH"
- Any other Overview surface

## Acceptance

- pytest count: 380 → ≥ 384 (+4 new backend tests)
- vitest count: 169 → ≥ 170 (+1 subtitle text change)
- `npm --prefix apps/web run typecheck` clean
- `npm --prefix apps/web run build` clean

## Files expected to change

| File | Δ LOC est | Reason |
|------|-----------|--------|
| `src/atlas20/api/data_access/overview.py` | +5/-10 | Simplify `_build_aum` |
| `tests/test_overview_data_access.py` | +30 | 4 new regression tests |
| `apps/web/src/features/overview/OverviewTab.tsx` | +1/-1 | Subtitle wording |
| `apps/web/src/features/overview/OverviewTab.test.tsx` | +8 | 1 new test for subtitle |

Total: ~40 LOC net change.
