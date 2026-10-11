# Live Research Console Design

## Goal

Adapt the web console to the current research and live-execution state, and repair all confirmed console defects. The console must distinguish frozen research evidence, out-of-sample tracking, and read-only live operations, and every exposed control must be exercised by an automated full-journey test.

## Current-state correction

`reports/latest` is a legacy report pointer and is not the authority for the current frozen spec. The authoritative current artifacts are:

- Spot signal and target: `reports/phase_momentum_live/latest_signal.json`
- Frozen H5 evaluation: `reports/phase_momentum_candidate_eval_h5/{decision_table.csv,deflated_sharpe.csv}`
- OOS tracking: `reports/phase_momentum_oos_2026/{manifest.json,oos_summary.csv,daily_returns.csv}`
- Derivatives execution: `reports/derivatives_track_execution/latest.json`
- Derivatives health: `reports/derivatives_track_live/{health.json,audit.json,signal_equivalence.json,journal.csv}`

The existing Overview remains a report workspace, but the new `Live Research` tab is the canonical current-state view. The legacy Overview hero wording must not imply that its report champion is the live frozen spec.

## API design

Add one read-only endpoint: `GET /api/live/research`.

It returns a versioned, typed payload with four sections:

1. `spot`: trial ID, spec, signal date, panel date, target/current weights, gross exposure, BTC gate, cost basis, rule, data-quality check, and frozen H5 decision metrics.
2. `oos`: start/end/days, selected 20 bps production result, BTC benchmark, stress-cost table, and data-quality interpretation.
3. `derivatives`: execution status, health, audit checks, signal-equivalence result, account equity, gross notional, and latest journal rows.
4. `artifacts`: source-relative artifact names and availability. No absolute paths or credentials are exposed.

The endpoint only reads files; it never places orders, mutates the database, or changes research state. Missing or malformed artifacts return structured availability information instead of silently showing fabricated data.

## Frontend design

Add an eighth top-level tab: `Live Research`.

The tab has four cards:

- **Spot research**: frozen spec, provisional status, signal date, target weights, current weights, gross exposure, BTC gate, and H5 metrics.
- **Out-of-sample tracking**: window, H5 multiple, BTC multiple, relative result, and cost-stress rows. It explicitly states that the short OOS window does not validate the strategy.
- **Derivatives live monitor**: health status, equity, gross notional, hard-failure count, audit checks, and signal equivalence.
- **Execution journal**: latest journal rows, including date, signal date, equity, position value, unrealized PnL, positions, trades, and notes.

A `REFRESH LIVE DATA` button refetches the read-only payload. No control in this tab mutates trading state.

## Confirmed defect repairs

1. Compare equity charts must convert backend multipliers to percentage returns. A value of `0.876` must display as `-12.4%`, not `-12.5` percentage points misread as `-12.5%`.
2. Backtest UI must not expose an ineffective `Slots` input. Slots are strategy-defined in the frozen research engine; the UI shows this as non-configurable and submits the schema-required value without implying user control.
3. Backtest default end date must come from the latest verified panel date, not the hardcoded `2026-05-18`.
4. Featured digest hero must expose and exercise MARKDOWN, PDF, PNG, CSV, and DOWNLOAD ALL. Download failures show an actionable error and re-enable the button.
5. All tabs and controls must be included in automated tests, including loading, empty, and error paths where applicable.

## Acceptance criteria

- `GET /api/live/research` reads the checked-in real artifacts and returns the current H5 and derivatives state without mutation.
- The frontend has eight navigation tabs; the Live Research tab shows real current data and does not claim validation that the research record does not support.
- Compare chart Y-axis values match percentage returns.
- Backtest no longer offers a misleading slots control and defaults to the latest verified end date.
- Featured digest format buttons perform authenticated blob downloads.
- Backend tests, frontend unit tests, Playwright full-journey tests, lint, type checks, OpenAPI snapshot check, and production build all pass.
- The full-journey test inventories every visible button, exercises every non-destructive interaction, and performs one real queue/report action per already-existing test pattern.
