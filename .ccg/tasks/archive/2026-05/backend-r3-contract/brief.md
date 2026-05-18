# Backend Task — Implement FastAPI to match R3 frontend contract

## Project context

- Repo: `D:/Code/Atlas20` (already cloned, branch `redesign/r3-premium`).
- Frontend: complete, in `apps/web/`. Contract lives in `apps/web/src/lib/api.ts` (TypeScript types + fallback mock data + fetch helpers).
- Backend: FastAPI app at `src/atlas20/api/`. Existing routes use an OLDER contract (champion / selection_history). We need to MIGRATE the API in-place to the new R3 contract. Old tests that target obsolete endpoints/fields should be rewritten — do not preserve dead contract.
- Frontend base path: all API calls go through `/api/...` (see `apps/web/src/lib/api.ts:511 buildApiUrl`).
- Pipeline / data layer code under `src/atlas20/{backtest,data,signals,strategies,...}` is NOT in scope. Backend serves mock data that mirrors the frontend's `fallback*` constants verbatim. Do not run real backtests.

## Goal

Backend returns JSON that exactly matches frontend TypeScript types so the live API can replace the frontend's `import.meta.env.MODE !== "test"` fallback path. All 6 pages (Overview, Backtest Studio, Strategy Compare, Run History, Universe & Data Health, Reports & Exports) must work end-to-end against the new API.

## Endpoint table (all under `/api` prefix)

| Method | Path | Request | Response |
|---|---|---|---|
| GET  | `/overview`                       | —                                              | `OverviewPayload` |
| GET  | `/options`                        | —                                              | `dict[str, Any]` (return `{}` is fine) |
| GET  | `/runs/queue`                     | —                                              | `list[RunRowSummary]` |
| GET  | `/runs`                           | query: `q, chips, dateRange, view, page, pageSize` | `{items: list[RunRow], total: int, page: int, pageSize: int}` |
| GET  | `/runs/{id}`                      | —                                              | `RunRow` |
| GET  | `/runs/{id}/detail`               | —                                              | `RunDetailPayload` |
| POST | `/runs/{id}/favorite`             | —                                              | `{run_id: str, favorited: bool}` (toggle) |
| POST | `/backtests/run`                  | body: `BacktestConfig`                          | `RunRowSummary` (new run, status="queued") |
| GET  | `/compare`                        | query: `ids` (comma-separated), `range` (1M/3M/YTD/1Y/ALL) | `ComparePayload` |
| GET  | `/universe/timeline`              | —                                              | `UniverseTimelinePayload` |
| GET  | `/universe/sources`               | —                                              | `list[DataSource]` |
| GET  | `/universe/alerts`                | —                                              | `list[DataAlert]` |
| POST | `/universe/refresh`               | —                                              | `{refreshed_at: str}` (ISO8601 UTC now) |
| GET  | `/reports/digest/featured`        | —                                              | `FeaturedDigest` |
| GET  | `/reports`                        | query: `sort` (recent/oldest/size/type)         | `list[ReportEntry]` (sorted server-side) |
| GET  | `/reports/digest/download`        | query: `format` (markdown/pdf/png/csv/bundle)   | `{url: str}` (return a placeholder URL like `/static/reports/digest.{ext}` — the file does not need to exist) |
| GET  | `/reports/{id}/download`          | query: `format` (markdown/pdf/png/csv, optional)| `{url: str}` (placeholder) |

## Files to create / modify

Replace OR create from scratch (do NOT preserve old shapes):

- `src/atlas20/api/schemas.py` — REPLACE. Define all Pydantic models corresponding to frontend types:
  - `ChampionSummary`, `StrategySummary`, `SeriesPoint`, `SelectionHistoryRow`
  - `Aum`, `StrategiesBreakdown`, `RegimeInfo`, `RebalanceInfo`, `EquityOverlay`, `HeroKpi` (or nest under OverviewPayload)
  - `OverviewPayload`
  - `RunStatusEnum` = Literal["queued","running","completed","failed"]
  - `RunWindow`, `RunRow`, `RunRowSummary`, `RunDetailPayload`
  - `BacktestConfig`, `HistoryFilter` (request)
  - `CompareMetrics`, `CompareOverlap`, `ComparePayload`
  - `UniverseTimelinePayload`, `DataSource`, `DataAlert`
  - `FeaturedDigest`, `ReportEntry`
  - Use `model_config = {"populate_by_name": True}` if needed; frontend uses snake_case for most types (verified — keep snake_case in JSON).
  - **Match field names EXACTLY**: e.g. `return_pct` (not `returnPct`), `max_dd` (not `maxDd`), `duration_s`, `eta_s`, `created_at`, `strategy_family`, `last_sync_seconds`, `generated_at`, `size_bytes`, `report_type`. BUT for `aum.deltaPct`, `aum.sparkline`, `strategies.total/breakdown`, `regime.{label,score,model}`, `rebalance.{ts,swaps:{out,in,deltaPct}}`, `equity_overlay.series:{ts,atlas,btc}`, `hero_kpi.{ytdReturn,sharpe,maxDd,winRate}`, the frontend uses **camelCase**. Verify each field name against `apps/web/src/lib/api.ts` lines 12-285.

- `src/atlas20/api/mock_data.py` — CREATE NEW. Mirror these frontend constants exactly into Python literals (copy values, not shape):
  - `fallback_overview` ← `apps/web/src/lib/api.ts:288-377`
  - `fallback_runs_queue` ← lines 379-386
  - `fallback_runs_list` ← lines 388-403 (14 rows)
  - `fallback_run_detail` ← lines 405-409 (use index 6 = btk_0142)
  - `fallback_compare` ← lines 411-444
  - `fallback_universe_timeline` ← lines 453-466 (`universeTickers` lines 446-451)
  - `fallback_data_sources` ← lines 468-478 (9 sources)
  - `fallback_data_alerts` ← lines 480-487 (6 alerts)
  - `fallback_featured_digest` ← lines 489-496
  - `fallback_reports` ← lines 498-505 (6 reports)
  - These are mutable module-level dicts/lists OK. POST `/runs/{id}/favorite` flips a boolean in `fallback_runs_list`. POST `/backtests/run` prepends a new `RunRowSummary` to `fallback_runs_queue`.

- `src/atlas20/api/services.py` — REPLACE. Pure functions that build response models from `mock_data`:
  - `get_overview() -> OverviewPayload`
  - `list_runs_queue() -> list[RunRowSummary]`
  - `list_runs(q, chips, date_range, view, page, page_size) -> tuple[list[RunRow], int]` — apply text search on `strategy`/`run_id`, filter by chips (chip matches `strategy_family` if in {"ATLAS","Momentum","MeanRev","Carry","Other"} or `status`), filter by date range (anchor = today's date `2026-05-19`, compute cutoff from `dateRange`), paginate.
  - `get_run(id) -> RunRow | None`
  - `get_run_detail(id) -> RunDetailPayload | None`
  - `toggle_run_favorite(id) -> dict | None`
  - `register_new_backtest(config: BacktestConfig) -> RunRowSummary` — synthesize `btk_XXXX` id (max+1), insert into queue with `status="queued"`, build `params_summary` like `"N=20 · Weekly · 2024→2026"`.
  - `get_compare(ids: list[str], range_: str) -> ComparePayload`
  - `get_universe_timeline()`, `get_data_sources()`, `get_data_alerts()`, `refresh_universe() -> dict`
  - `get_featured_digest()`, `list_reports(sort) -> list[ReportEntry]`, `build_digest_download_url(fmt)`, `build_report_download_url(id, fmt)`
  - Keep `get_options_payload()` (existing) but return `{}` or simple defaults.

- `src/atlas20/api/routes/overview.py` — REPLACE response_model to `OverviewPayload`; delegate to `services.get_overview()`.

- `src/atlas20/api/routes/runs.py` — REPLACE. Implement:
  - `GET /runs/queue` BEFORE `GET /runs/{id}` (route ordering matters in FastAPI).
  - `GET /runs` with query params (q, chips as comma-string → split, dateRange, view, page, pageSize).
  - `GET /runs/{id}` with 404 on miss.
  - `GET /runs/{id}/detail` with 404.
  - `POST /runs/{id}/favorite` with 404 on miss.
  - Drop existing pandas/CSV artifact routes (`/runs/{id}/{artifact}`) — they are obsolete.

- `src/atlas20/api/routes/backtests.py` — REPLACE. `POST /backtests/run` accepts `BacktestConfig`, returns `RunRowSummary`. Drop the `GET /backtests` placeholder.

- `src/atlas20/api/routes/compare.py` — NEW.
- `src/atlas20/api/routes/universe.py` — NEW.
- `src/atlas20/api/routes/reports.py` — NEW.

- `src/atlas20/api/app.py` — register new routers (compare, universe, reports). Keep CORS for `http://localhost:5173` and `http://127.0.0.1:5173`.

- `src/atlas20/api/runner.py` — likely orphaned by new contract. Inspect; if only the old CSV-artifact backtest pathway uses it, delete it (and any imports).

## Tests

- `tests/test_api_routes.py` — REWRITE. One test per endpoint:
  - status 200
  - response JSON validates against the new schema
  - key fields present (spot-check a few representative values from mock data)
- `tests/test_api_services.py` — REWRITE for new service functions:
  - filtering: q="ATLAS" returns only ATLAS rows; chips=["completed"] filters by status
  - pagination: page=1 pageSize=5 yields 5 items, page=2 yields the next batch
  - favorite toggle is idempotent (call twice returns to original)
  - sort_reports recent / oldest / size / type each produce expected first id
- `tests/test_api_runner.py` — DELETE if its assumptions (CSV runs dir, real engine execution) are obsolete. If it can be salvaged into a `/backtests/run` smoke test, do so; otherwise delete.

Run `pytest -q` and ensure all green. Add `httpx` to test deps if missing (already in `pyproject.toml` dev extras per current state — verify).

## Acceptance criteria

1. `python -m uvicorn atlas20.api.app:app --reload` boots without import errors.
2. `pytest -q` is all green.
3. `curl http://localhost:8000/api/overview | jq '.hero_kpi.ytdReturn'` returns `12.4756`.
4. `curl http://localhost:8000/api/runs/queue | jq 'length'` returns `6`.
5. `curl 'http://localhost:8000/api/runs?page=1&pageSize=14&dateRange=all&q=&chips=&view=list' | jq '.items | length'` returns `14`.
6. `curl http://localhost:8000/api/runs/btk_0142/detail | jq '.kpi.sharpe'` returns `3.42`.
7. `curl 'http://localhost:8000/api/compare?ids=atlas,momentum,meanrev&range=YTD' | jq '.metrics.cagr.atlas'` returns `1.584`.
8. `curl http://localhost:8000/api/universe/alerts | jq 'length'` returns `6`.
9. `curl http://localhost:8000/api/reports/digest/featured | jq '.defaultFormat'` returns `"markdown"`.

## Constraints

- Keep `/api` prefix on every router.
- Keep CORS for vite dev ports.
- Use Pydantic v2 syntax (`model_config`, `Field(...)`, `model_validator`). Project already uses pydantic>=2.8.
- Use Python 3.11 syntax (`X | None`, `list[T]`).
- Do NOT add new pip dependencies beyond what's in `pyproject.toml` (fastapi, pydantic, pandas, httpx).
- Do NOT introduce a database. Mock data lives in module-level Python data structures.
- Field name parity is critical — when in doubt, check `apps/web/src/lib/api.ts` line by line.

## Deliverables

When done:
1. Commit with message `feat(api): R3 contract backend — schemas + mock services + routes + tests`.
2. Write a brief `review.md` summarizing files changed, test counts, and any deviations.
