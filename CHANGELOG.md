# Changelog

All notable changes to the Atlas20 Rotation research console.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Known UI gaps (B23 candidates)

- Overview "Equity Curve · YTD" chart renders empty (legend visible, lines missing) when champion's window is outside the current YTD range.
- Overview equity overlay legend hardcoded `"ATLAS Adaptive v3" / "BTC Benchmark"`; should reflect the real champion strategy name.
- Overview "Latest Rebalance" subtitle hardcodes `"weekly"` regardless of the cadence the most-recent backtest actually ran.
- Tracked Notional sparkline shows the champion strategy's tail while the headline number is the sum across all strategies — value source and sparkline source are inconsistent.

## [0.2.0] — 2026-05-21

Major release covering the **B16 → B22** ship-audit sweep: the research console now reads real backend artifacts on every surface, the worker process is observable end-to-end, and 264 commits' worth of correctness fixes have landed under the alternating dual-reviewer protocol (Opus + codex).

### Added

- **Worker queue-loop heartbeat gauge** (`atlas20_worker_last_poll_timestamp_seconds`) with `multiprocess_mode="max"`; docker-compose worker healthcheck now scrapes `/metrics` and fails if the gauge is stale (>30s) so a stuck queue loop is caught even when the listener thread is still serving. Heartbeat thread also stamps the gauge during in-flight runs so long backtests are not falsely killed.
- **Worker `/metrics` endpoint** on port 8001 with `PROMETHEUS_MULTIPROC_DIR` aggregation, so per-run subprocess counter increments survive subprocess exit. Bootstrap shim wipes the multiproc dir on startup to prevent unbounded growth.
- **Real Overview payload** (replacing the prior `mock_data.fallback_overview` dispatcher): `strategies.breakdown` counts real families from `strategy_summary.csv`; `regime.label` derives from the latest row of `regime_frame.csv` across `data/processed/<preset>/` and root paths; `rebalance.swaps` diffs the last two rebalance dates in `selection_history.csv`; `aum.current` is the sum of `equity_curves.csv` final values across tracked strategies (research-only "TRACKED NOTIONAL", UI labeled to avoid AUM confusion).
- **Lifespan shadow-install warning**: detects when `pip install .` plants atlas20 in site-packages and the user's edits to `src/` would silently be ignored. Worker and API both emit. Extracted to `atlas20.api.install_check` so the worker doesn't drag in FastAPI/middleware.
- **Backtest preset dropdown** loads 30 real preset names from `/api/options`; falls back to `config/*.yaml` slugs on fresh install rather than hardcoded "ATLAS Adaptive v3" / "Momentum Top-10" placeholders that don't map to any real config.
- **Compare seed-once-from-real-presets**: chips populate from the first `/api/options` response after a single network roundtrip, then `seededRef` prevents background refetches from clobbering user edits.
- **Backtest prefill fallback chain**: `prefillRunId → queue.data[0].run_id → recentRunsQuery.items.find(status="completed" && return_pct != null && strategy != "universe_refresh").run_id → empty state`. Removes the previous "btk_0142" literal that 404'd on every fresh visit.
- **End-to-end UI ↔ backend wiring**: Overview hero champion title reads `champion.strategy` from the payload (was hardcoded "ATLAS Adaptive v3"); all six tabs verified live against real data.

### Fixed

- **`PROMETHEUS_MULTIPROC_DIR` wipe-on-startup** prevents unbounded per-pid mmap file growth across worker restarts. `spawn.py` coordinates a once-only wipe and sets `ATLAS20_WORKER_MULTIPROC_SKIP_WIPE=1` on children.
- **`start_metrics_server` OSError narrowing**: only swallows `EADDRINUSE`/`WSAEADDRINUSE`; other OSErrors (`PermissionError` for low ports, network-unreachable, etc.) re-raise instead of being silently swallowed. Warns when port collision happens without a configured multiproc dir (counters would be silently dropped).
- **`run_one` writes `reports/latest.txt` to the final path** (not the `.tmp` path the pipeline wrote during `export_result_tables`) so `/api/compare`'s `_latest_report_dir` resolves the correct directory after a fresh backtest, rather than falling back to mock data.
- **`config_adapter` constrains strategy frequencies to the chosen rebalance cadence** AND preserves the hardcoded benchmark `"monthly"` lookup. Without this Weekly/Biweekly user choices either crashed (`int("biweekly")` in `calendar.py`) or surfaced misleading "Unsupported rebalance frequency" errors. Minimized lookup table to `{chosen_freq, monthly}` so pipeline doesn't materialize unused universe snapshots.
- **`data/processor.py` extends panel by `min_history_days` before backtest start** so universe eligibility can be computed; `pipeline.py` then slices `market.returns` to `[start_timestamp, end_timestamp]` before each `run_backtest` call so daily_returns doesn't inherit the buffer's zero-return rows. Sharpe was ~22% diluted in our test before this fix.
- **Reporting**:
  - graceful N/A fallback in `build_markdown_report` when benchmark strategies are absent from `summary`.
  - scope line derived from `config.strategies.{momentum,sector}_frequencies` instead of hardcoded "monthly and biweekly".
  - `yearly_return_table.index.name = "year"` so CSV header is meaningful and `_read_indexed_csv` consumers don't see `"Unnamed: 0"`.

### Docs

- `docs/operations/logging.md` Prometheus section accurately describes per-process metric ownership, multiproc aggregation, Windows port-bind semantics, and the new heartbeat-based healthcheck.
- `docs/operations/worker.md` rewritten for accurate PID-recovery semantics and the new healthcheck gauge.
- `docs/redesign/ROADMAP.md` Phase O (observability) ticked through O1-O5 — all shipped.

### Quality gates

- **pytest**: 368 passed (was 356 at B15 ship audit start). Includes new regression tests for: worker poll-tick gauge invocation, heartbeat-thread gauge advance, real run_one subprocess multiproc aggregation, config-adapter cadence constraint, processor pre-window buffer, fresh-install preset slugs, report scope cadence derivation, Compare seed-from-real-presets, defaults preserving on options refetch.
- **vitest**: 163 passed (was 161). Direct cold-load Compare seeding regression + cross-cadence assertions.
- **CI**: all jobs green on `main` (Ruff, Python, mypy, web typecheck, web tests/build, dependency security scan).

### Observability

Workers and API are now scrape-targets for Prometheus with a documented metric inventory (`http_requests_total`, `atlas20_backtests_total`, `atlas20_backtest_duration_seconds`, `atlas20_report_generations_total`, `atlas20_rate_limit_hits_total`, `atlas20_worker_last_poll_timestamp_seconds`). See `docs/operations/logging.md` for scrape configuration.

### Internal

- `.gitignore` extended to ignore pipeline-generated `data/processed/`, raw provider snapshots in `data/raw/`, design mockups in `output/imagegen/`, SQLite WAL sidecars, scheduler lock, and multiproc dirs. Repository drops from 854 to 625 tracked files (~120MB lighter on disk).
- CI Web typecheck job switched to `npm run typecheck` (project-references mode) — the prior `tsc --noEmit -p tsconfig.json` was misinterpreted by `npm exec`.
- Migration `0042_report_files_run_id_set_null` for the report-files / runs FK behavior.
- `ATLAS20_API_KEYS=[]` retained as the MVP authentication posture; production deployments must populate the env array.

## [0.1.0] — 2026-05-17

Initial public release. See git history before the 264-commit redesign sweep for the pre-B16 baseline.
