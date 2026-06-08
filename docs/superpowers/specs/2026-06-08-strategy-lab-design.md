# Strategy Lab Design

## Goal

Build the first Strategy Lab slice for Atlas20: a console tab that lets a researcher launch a small parameter matrix, monitor the resulting batch, and review ranked completed runs.

The feature is focused on research workflow and presentation. It does not change deployment, image publishing, or production infrastructure.

## Current Context

Atlas20 already has the pieces Strategy Lab needs:

- `BacktestConfig` validates one run request.
- `POST /api/backtests/run` persists one queued run through `register_new_backtest`.
- The worker executes queued runs and writes artifacts under `reports/app_runs/`.
- Run History lists queued, running, completed, failed, and cancelled runs.
- Compare can compare strategies or fallback data from report artifacts.

The missing product workflow is batch exploration: users can only submit one backtest at a time and then manually inspect history.

## Product Scope

Strategy Lab MVP adds one new console tab named `Strategy Lab`.

The first version supports:

- Matrix controls for `preset`, `universe.topN`, and `window.rebalance`.
- Read-only defaults for date window, allocation, fees, and slippage inherited from `defaultBacktestConfig`.
- A run-count preview before submission.
- A guarded submit action that queues every matrix combination as an ordinary backtest run.
- A batch summary that shows queued, running, completed, failed, and cancelled counts.
- A ranked results table based on completed runs in the batch.
- Empty, loading, error, retry, and queued-success states.

The MVP intentionally excludes:

- A custom high-performance optimization engine.
- Bayesian search, genetic search, or walk-forward optimization.
- Heatmaps across multiple metrics.
- New report artifact formats.
- Changes to worker process behavior.

These can be added after the matrix workflow is stable.

## User Experience

The tab should feel like an operational research tool, not a marketing page.

Layout:

- Top band: compact experiment controls and run-count preview.
- Middle band: batch status summary with count pills.
- Bottom band: ranked completed runs table.

Controls:

- Preset multi-select from `/api/options.presets`.
- Universe size toggle group from `/api/options.universes`, initially `[10, 20]` when available.
- Rebalance toggle group from `/api/options.rebalances`, initially `["Weekly", "Biweekly", "Monthly"]`.
- Metric sort select for `Sharpe`, `CAGR`, `Calmar`, and `Max DD`.
- Submit button disabled when no combinations are selected or a submission is pending.

The user should be able to:

1. Select a small matrix.
2. See how many runs will be queued.
3. Submit the batch.
4. Watch status counts update.
5. Sort completed results by risk/return metric.
6. Click a completed run to open Backtest Studio with that run.

## Backend Design

Add a small Strategy Lab API surface rather than overloading `/api/backtests/run`.

Schemas:

- `StrategyLabMatrixRequest`
  - `presets: list[str]`
  - `topNs: list[int]`
  - `rebalances: list["Weekly" | "Biweekly" | "Monthly"]`
  - `baseConfig: BacktestConfig`
- `StrategyLabBatchResponse`
  - `batch_id: str`
  - `runs: list[RunRowSummary]`
  - `total: int`
- `StrategyLabBatchPayload`
  - `batch_id: str`
  - `status_counts: dict[str, int]`
  - `runs: list[RunRow]`
  - `results: list[StrategyLabResult]`

Persistence:

- Do not add a new table for MVP.
- Add a nullable `strategy_lab_batch_id` column to `runs`.
- Keep `Run.params` as pure `BacktestConfig` JSON so the worker can keep strict parsing unchanged.
- Generate `batch_id` as `lab_YYYYMMDDHHMMSS_<short_hash>`.

Routes:

- `POST /api/strategy-lab/batches`
  - Expands the matrix into `BacktestConfig` objects.
  - Validates each config through the existing `BacktestConfig` and `to_research_config` path.
  - Calls the same service path that ordinary backtests use.
  - Returns the batch id and run summaries.
- `GET /api/strategy-lab/batches/{batch_id}`
  - Reads runs whose `strategy_lab_batch_id` matches the batch id.
  - Builds status counts.
  - Builds ranked result rows from completed runs with available metrics.

Batch size:

- Limit MVP submissions to at most 24 runs per request.
- Reject empty matrices and oversized matrices with HTTP 422.

## Frontend Design

Add a feature folder:

- `apps/web/src/features/strategy-lab/StrategyLabTab.tsx`
- `apps/web/src/features/strategy-lab/StrategyLabControls.tsx`
- `apps/web/src/features/strategy-lab/StrategyLabResultsTable.tsx`
- `apps/web/src/features/strategy-lab/strategyLab.ts`

Add API helpers in `apps/web/src/lib/api.ts`:

- `submitStrategyLabBatch(request)`
- `getStrategyLabBatch(batchId)`
- TypeScript types matching the backend payloads.
- Fallback data for tests and initial empty states only.

Navigation:

- Add a `strategyLab` console tab between Backtest and Compare.
- Tab label: `Strategy Lab`
- Header subtitle: `Parameter matrix + ranked experiment results`

Polling:

- After a batch is submitted, poll `GET /api/strategy-lab/batches/{batch_id}` every 5 seconds while any run is queued or running.
- Stop polling once all runs are terminal.

Navigation from results:

- Clicking `Open` on a result calls `onNavigate("backtest", run_id)`.

## Data Flow

1. `StrategyLabTab` loads `/api/options`.
2. Controls build a matrix from selected presets, universe sizes, and rebalances.
3. Submit builds `StrategyLabMatrixRequest` using `defaultBacktestConfig` as the base.
4. Backend expands and queues runs.
5. Frontend stores the returned `batch_id`.
6. Query polling fetches the batch payload.
7. Results table ranks completed runs by the selected metric.

## Error Handling

- Empty matrix: inline disabled state plus helper text.
- Oversized matrix: backend 422, frontend error banner.
- Options load failure: controls use fallback options and show the existing demo-data style pattern if needed.
- Submit failure: keep selections intact and show an error banner.
- Batch fetch failure: keep last successful batch payload visible and show retry.
- Runs with missing metrics stay visible in status counts but are omitted from ranked results.

## Testing

Backend tests:

- Matrix expansion queues the expected number of runs.
- Empty matrix is rejected.
- Oversized matrix is rejected.
- Batch fetch returns status counts and completed result rows.
- Batch ids are scoped through run params and do not include unrelated runs.

Frontend tests:

- Strategy Lab tab renders controls and run-count preview.
- Submit calls `submitStrategyLabBatch` with the expected matrix.
- Batch status counts render after submission.
- Results table sorts by Sharpe, CAGR, Calmar, and Max DD direction.
- Open result navigates to Backtest Studio with the run id.
- Loading, error, and empty states render accessibly.

End-to-end test:

- The console can open Strategy Lab, submit a small matrix, and see a queued batch status using the live API.

## Acceptance Criteria

- A user can submit a small Strategy Lab matrix without leaving the console.
- The queued runs appear as ordinary backtests and remain compatible with History, Backtest Studio, Reports, and worker processing.
- The Strategy Lab tab shows batch status and ranked completed results.
- Existing single-run Backtest behavior remains unchanged.
- Verification passes for backend tests, frontend tests, typecheck, build, OpenAPI check, and Playwright smoke coverage.
