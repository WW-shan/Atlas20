# Changelog

All notable changes to the Atlas20 Rotation research console.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### B24 — Centralized display names + fallback data indicator (2026-05-25)

Two systemic bugs from live browser audit: raw strategy slugs leaking into every dropdown/pill/table header, and no visual indicator distinguishing real research data from hardcoded mock fallbacks.

**Added**
- `_format_display_name` centralized in `_common.py` with family-prefix mapping + `_DISPLAY_NAME_OVERRIDES` for `"base"` → `"Base Config"` and `"universe_refresh"` → `"Universe Refresh"`.
- `PresetOption(slug, display_name)` and `StrategyOption(strategy, display_name)` schemas. `/api/options` and `/api/compare` now return `display_name` for every entry.
- `data_source: "real" | "fallback"` discriminator on `OverviewPayload`, `ComparePayload`, `UniverseTimelinePayload`, and `DataAlert.source`.
- `DemoDataBanner` component (amber `⚠ DEMO DATA` banner) rendered on Overview, Compare, Universe, Reports tabs when `data_source === "fallback"`.
- Overview sync dot turns amber when `last_sync_seconds > 86400` (> 1 day stale).
- Overview KPI row gap increased to 32px for breathing room.

**Fixed**
- Backtest preset dropdown now shows `display_name` (e.g. "Base Config") instead of raw slug (`"base"`).
- Compare strategy pills, chart legend, and table headers now show `display_name` instead of raw slug.
- Error banner in Compare now renders even when data is unavailable (was hidden inside data-dependent branch).
- Removed `fallbackCompare` as `initialData` for Compare query — mock data no longer flashes on first paint.

**Removed**
- `DEFAULT_SELECTIONS`, `PRESET_COMPARE_IDS`, `__TEST_DEFAULT_SELECTIONS` from `StrategyCompareTab.tsx` (dead code from B22 era).

**Tests**
- pytest: 384 → 392 (+8). Display name unit tests, options/compare payload display_name tests, data_source real/fallback tests.
- vitest: 170 passed (test updates for new preset type, no count change).

### B23a — Overview UX honesty + chart empty state (2026-05-22)

Closes three of the four known B23 UI lies plus four new findings from the post-v0.2.0 dual-reviewer audit. Sixth commit on `feat/b23a-overview-honesty`: builder `dd640af` plus reviewer-pass commits `b246ef4` (F1 aria), `6f53d4a` (F2 path-validation reuse), `ea087a8` (F3 edge tests), `6b139b2` (F4 cadence-token precedence), `3355fef` (F5 NaN-only YTD).

**Added**
- `ChampionSummary.display_name` — friendly strategy name derived via `_format_display_name` (family prefix → "Momentum Rotation · ..." / fallback to title-cased slug). Rendered in Overview hero `<h2>` instead of raw strategy column header.
- `OverviewPayload.last_sync_seconds` — seconds since the resolved report dir's mtime; `_compute_last_sync_seconds` delegates to `_latest_report_dir` so the shared `relative_to(report_root)` guard handles pointer validation in one place.
- `EquityOverlay.atlas_label` / `EquityOverlay.btc_label` — payload-driven strategy + benchmark labels for the chart legend.
- `_parse_cadence` populates `ChampionSummary.rebalance_frequency` (was always `None`). Slug match first (`_biweekly_` / `_weekly_` / `_monthly_` / `_14D_` / `_7D_` / `_30D_`), fall back to median diff of unique rebalance dates in selection_history.
- `OverlayLineChart` empty-state copy ("No data in selected range") when `series.length === 0` — replaces the prior blank-SVG silent-fail.
- `frontend formatRelativeAge(seconds)` helper with 60s / 3600s / 86400s boundaries.

**Fixed**
- Overview equity overlay legend now follows `champion.display_name` and `"BTC Benchmark"` — no more hardcoded `"ATLAS Adaptive v3"`.
- Overview rebalance subtitle now renders `champion.rebalance_frequency ?? "—"` — no more hardcoded `"weekly"`.
- Equity Curve title now reads `EQUITY CURVE · ${range}`; backend falls back to `range="ALL"` when the YTD slice is empty (either temporally or after dropna) so the title is honest about what's shown.
- Card and chart `ariaLabel`s now derive from `equity_overlay.range`/`atlas_label`/`btc_label` — screen readers no longer announce "YTD" when range is "ALL".
- Removed the disabled `1M/3M/YTD/1Y/ALL` range tablist (decorative, all `disabled`, hardcoded active=YTD). Will return when wired to real backend range-switching.

**Tests**
- pytest: 368 → 380 (+12). New regression tests cover all 5 new helpers + 4 edge cases (clock skew, escaping pointer, duplicate rebalance dates, NaN-only YTD via dropna).
- vitest: 163 → 169 (+6). Display name in hero, payload-driven chart legend, payload-driven rebalance cadence, `formatRelativeAge` boundaries, chart empty-state copy, range-driven aria labels.

**Cross-validation matrix (Opus 4.7 + codex)**
- Round 1: Opus APPROVE 92/100, codex REQUEST_CHANGES 84/100 → 4 findings (F1-F4)
- Round 2: Opus APPROVE 96/100, codex REQUEST_CHANGES 90/100 → 1 finding (F5, NaN-only YTD subcase)
- Round 3: Opus APPROVE 96/100, codex APPROVE 100/100 → 0 findings ✅

### B23b — Tracked Notional champion-only headline (2026-05-22)

Closes the last B23 UI lie: the "Tracked Notional" card headline now shows the champion strategy's last equity value instead of the sum across all strategies. The sparkline, delta%, and headline are now all champion-sourced.

**Fixed**
- `_build_aum` headline (`aum.current`) changed from sum of all strategies' final equity to champion's last equity value. All three card values (headline, sparkline, delta%) now derive from the same source.
- Frontend subtitle changed from "{deltaPct} champion over 14 samples" to "{deltaPct} over last 14 data points".
- Card `ariaLabel` changed from "Tracked notional across all strategies (research)" to "Champion equity trend (research)".

**Tests**
- pytest: 380 → 384 (+4). Champion-only current, sparkline, delta%, empty fallback.
- vitest: 169 → 170 (+1). Subtitle wording.

**Cross-validation:** Opus APPROVE 95/100, codex APPROVE 92/100 → 0 findings requiring code changes.

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
