# Batch 3 Brief — R1 Overview + R5 Featured Digest (real data integration)

## Repo / branch
- `D:/Code/Atlas20`, branch `redesign/r3-premium`, HEAD `d2f522d`
- Roadmap reference: `docs/redesign/ROADMAP.md` Phase R1, R5

## Goal
Replace the hardcoded `mock_data.fallback_overview` payload with values derived
from real CSV outputs in `reports/latest/`. The frontend must keep working
unchanged — same JSON shape, just real numbers.

## Data sources (verified to exist)
- `reports/latest/strategy_summary.csv` — 30 strategies with metrics
- `reports/latest/equity_curves.csv` — daily equity for all strategies
- `reports/latest/daily_returns.csv` — daily returns for all strategies
- `reports/latest/yearly_returns.csv` — yearly aggregates
- `reports/latest/atlas20_report.md` — featured digest source

## Changes

### New: `src/atlas20/api/data_access/overview.py`
Module that reads CSVs and returns a fresh `OverviewPayload` dict each call
(or raises clear errors when CSVs are missing).

```python
def load_overview_from_reports(settings: Settings) -> dict:
    """Build OverviewPayload from reports/latest/*.csv. Reads each call —
    no caching; the caller may wrap with @lru_cache or rely on a query cache.
    Raises FileNotFoundError with actionable message if a required CSV missing.
    """
```

Sub-helpers (private):
- `_load_strategy_summary(report_root: Path) -> pd.DataFrame` — reads CSV,
  validates expected columns
- `_load_equity_curves(report_root) -> pd.DataFrame`
- `_load_daily_returns(report_root) -> pd.DataFrame`
- `_pick_champion(summary_df) -> pd.Series` — highest sharpe row
- `_build_top_strategies(summary_df, n=3) -> list[dict]`
- `_compute_ytd_return(daily_returns_col, anchor_date) -> float` —
  product of (1 + daily_return) from Jan 1 of anchor_date.year to anchor_date,
  minus 1
- `_compute_hero_kpi(daily_returns_col, summary_row, anchor_date) -> dict` —
  YTD ytdReturn (from daily_returns); sharpe + maxDd from summary_row;
  winRate = fraction of positive daily returns YTD
- `_build_equity_curve(equity_curves_col) -> list[dict]` — resample to month
  end, take 6 most recent points
- `_build_equity_overlay(equity_curves_df, champion_col, anchor_date) -> dict` —
  champion vs BTC_BH__always_on, return cumulative return % (not raw equity)
  for each month, range="YTD"
- `_build_rebalance(daily_returns_index, summary_row) -> dict` — last
  rebalance_date from daily_returns last row, with mock swaps (no real
  selection_history join yet — that's R2 territory)
- `_build_aum_strategies_regime() -> dict` — for now, return the same
  half-mock values as `fallback_overview` (no real data source for these yet,
  documented in code)

### Modify: `src/atlas20/api/services.py`
- `get_overview()` — read settings.report_root; try real data first; on
  FileNotFoundError fall back to `mock_data.fallback_overview` with a single
  warning log line. Never crash.
- `get_featured_digest()` — find newest `*.md` in `settings.report_root`
  recursive; build FeaturedDigest with real `generated_at` from file mtime,
  `subtitle` includes real champion strategy + YTD computed from R1
  - Fallback to mock if no .md found

### Settings additions
- Already have `settings.report_root` — verify it's used (not `Path("reports")`
  hardcoded)
- Already have `settings.anchor_date` — use it for `_today()` consistency

## Frontend contract
**CRITICAL**: don't break existing OverviewPayload TypeScript shape. The 30 fields
in `apps/web/src/lib/api.ts:OverviewPayload` must all be present and same types.

Manually re-derive only:
- `champion.strategy / multiple / cagr / sharpe / max_drawdown / annualized_turnover / monthly_win_rate / ending_equity` — from strategy_summary.csv
- `top_strategies[]` — sharpe top 3
- `equity_curve[]` — from equity_curves.csv (champion column, monthly resample)
- `daily_returns[]` — from daily_returns.csv (champion column, monthly resample)
- `hero_kpi.ytdReturn / sharpe / maxDd / winRate` — computed
- `equity_overlay` — champion vs BTC_BH__always_on
- `rebalance.ts` — last date in daily_returns

Keep mock values (no real source):
- `aum.{current, deltaPct, sparkline}` — annotate `# TODO(P2): real source`
- `strategies.{total, breakdown}` — annotate
- `regime.{label, score, model}` — annotate
- `rebalance.swaps` — annotate
- `selection_history` — defer to R2/X2 integration
- `champion.window_start, window_end` — derive from equity_curves index
- All `champion.*` weight fields — leave None (Pydantic nullable)

## Tests
New `tests/test_overview_data_access.py`:
- `load_overview_from_reports` produces a payload that passes `OverviewPayload.model_validate`
- Champion strategy is the one with highest sharpe in input CSV
- `top_strategies` length = 3
- `equity_curve` length = 6 (monthly resample of ~5 years of data)
- `hero_kpi.ytdReturn` computed correctly for known anchor_date + known daily_returns
  (use small synthetic CSV: 30 days of daily returns, anchor_date = day 30,
  YTD = product - 1)
- Missing CSV → FileNotFoundError with the missing path in message
- Empty CSV → ValueError

New `tests/test_services_overview_fallback.py`:
- When report_root has CSVs → real data returned (champion matches expected)
- When report_root is empty → falls back to mock with warning logged
- When CSV malformed → falls back to mock with warning logged

Update `tests/test_api_routes.py` — the existing `test_overview_endpoint_returns_r3_payload`
test depends on `fallback_overview.hero_kpi.ytdReturn == 12.4756`. Either:
- Add a fixture that sets `settings.report_root` to a tmp empty path so fallback
  is used, OR
- Replace assertion with structural check (payload validates as
  `OverviewPayload` and has hero_kpi with all keys present)

Featured digest tests — separate `tests/test_featured_digest.py`:
- Real .md present → subtitle contains champion strategy name
- No .md → falls back to mock
- Newest .md is selected (mtime-based)

## Acceptance
1. `pytest -q tests/` — all green (existing + new)
2. `python -c "from atlas20.api.services import get_overview; p = get_overview(); print(p.champion.strategy, p.hero_kpi.ytdReturn)"`
   — prints real values (likely `BTC_BH__always_on 0.xxxx` or similar based
   on which strategy has highest sharpe in current reports/latest)
3. Live curl `GET /api/overview` returns valid JSON, passes frontend's
   `OverviewPayload` type at runtime (TS check by hand: `console.log(d.champion.strategy)`)
4. Frontend vitest 106/106 still pass (run `npm test --prefix apps/web -- --run`)

## Commit
Single commit:
```
feat(api): R1/R5 real-data overview + featured digest with mock fallback
```

Body lists: new module, fallback behavior, tests added, frontend compatibility note.

## Out of scope (later batches)
- Persistent caching (Phase P will add proper repository layer)
- Universe / data sources / reports archive (R4/R6/R8)
- Real selection_history join (R2 needs Phase P first)
- `aum` / `regime` real source (no data source exists yet)

## After commit
Write `.ccg/tasks/batch-3-overview/review.md` summarizing files, tests, manual
smoke result with the actual champion strategy name shown.
