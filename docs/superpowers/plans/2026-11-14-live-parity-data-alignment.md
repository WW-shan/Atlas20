# LS45-G125 实盘/回测/数据全链路对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 LS45-G125 的信号、数据、回测、实盘执行、对账和监控统一到 `D+1 01:05 UTC`，并新增 live-parity 与数据可靠性审计。

**Architecture:** 在 `DerivativeBacktestConfig` 增加分钟级执行、合约量化、每日保证金归一化和审计输出；LS45 runner 显式使用 01:05；新增独立 data audit 模块和脚本；实盘 manifest 记录并校验执行时钟与数据哈希；旧 03:00 报告复制保留，新 01:05 报告作为主报告。

**Tech Stack:** Python 3.11, pandas, pytest, existing Bitget public/private clients, launchd/systemd, React frontend unchanged.

**Spec:** `docs/superpowers/specs/2026-11-14-live-parity-data-alignment-design.md`

## Global Constraints

- 唯一成交时钟：`D+1 01:05 UTC`。
- 不删除旧 03:00 结果；新结果必须并列展示。
- 不使用未来数据、不填零、不静默丢弃缺失资产。
- 20bps 为验收主成本；6bps 只做敏感性。
- 实盘 promotion 仍需负责人批准；本计划不自动放宽任何现有门禁。
- 每个任务结束运行相关测试；最终运行 `make test`、`make lint`、`make typecheck`、`make build`。
- 每个实质里程碑提交并推送 `main`。

---

### Task 1: 统一执行时钟与分钟级回测

**Files:**
- Modify: `src/atlas20/derivatives/engine.py`
- Modify: `src/atlas20/derivatives/live_chain.py`
- Test: `tests/test_derivatives_engine.py`
- Test: `tests/test_derivatives_live_chain.py`

**Interfaces:**
- Produces: `DerivativeBacktestConfig.execution_minute: int = 0`
- Produces: `DerivativeBacktestConfig.execution_price_snap: str = "exact"`
- Produces: `LIVE_EXECUTION_UTC = time(1, 5)` and `execution_utc_text() -> str` in `live_chain.py`
- Consumes: existing `_execution_time` and `_resolve_time`

- [ ] Write a failing test that a signal on `2026-11-13` with `execution_hour=1, execution_minute=5, execution_price_snap="floor"` executes on the `2026-11-14 01:00` mark bar.
- [ ] Write a failing test that `execution_minute=5, execution_price_snap="exact"` raises a clear missing-mark error when only hourly bars exist.
- [ ] Run `pytest tests/test_derivatives_engine.py -q` and confirm failure.
- [ ] Add `execution_minute` validation `[0, 59]` and `execution_price_snap` choices `exact|floor|ceil`.
- [ ] Update `_execution_time` to include minutes.
- [ ] Add `_resolve_execution_bar` that floors/ceils to the containing available hourly bar and never silently jumps more than one hour.
- [ ] Add shared `LIVE_EXECUTION_UTC = time(1, 5)` and use it in `live_execution_hint_for_signal`.
- [ ] Run targeted tests and commit `feat: add 01:05 execution clock`.

### Task 2: LS45 target ledger and manifest use 01:05

**Files:**
- Modify: `scripts/run_derivatives_shadow.py`
- Modify: `scripts/run_ls45_live_signal.py`
- Modify: `scripts/run_h5_regime_short_router.py`
- Modify: `src/atlas20/derivatives/live_chain.py`
- Test: `tests/test_run_ls45_live_signal.py`
- Test: `tests/test_derivatives_live_chain.py`
- Test: `tests/test_audit_signal_equivalence.py`

**Interfaces:**
- Produces: `_execution_hint(signal) -> signal.normalize() + 1 day + 01:05`
- Produces: manifest keys `execution_utc`, `execution_price_model`, `execution_source`
- Consumes: `LIVE_EXECUTION_UTC`

- [ ] Write failing tests asserting every LS45 `execution_hint` is `D+1 01:05` and manifest has `execution_utc="01:05"`.
- [ ] Add `--execution-hour` and `--execution-minute` to shadow/router runners, defaulting to `3/0` for legacy tracks, with LS45 wrapper passing `1/5`.
- [ ] Change LS45 `_execution_hint` to `01:05`; update `_targets_executing_after` docstring.
- [ ] Add `execution_utc` and `execution_price_model=mark_1h_open_floor` to LS45 manifest.
- [ ] Update `send_derivatives_signal.py` expected hint to 01:05 and labels.
- [ ] Run `pytest tests/test_run_ls45_live_signal.py tests/test_derivatives_live_chain.py tests/test_audit_signal_equivalence.py -q`.
- [ ] Commit `feat: align LS45 research ledger to 0105 UTC`.

### Task 3: live-parity engine features

**Files:**
- Modify: `src/atlas20/derivatives/engine.py`
- Modify: `scripts/run_derivatives_shadow.py`
- Modify: `scripts/run_h5_regime_short_router.py`
- Test: `tests/test_derivatives_engine.py`
- Test: `tests/test_derivatives_execution.py`

**Interfaces:**
- Produces: `DerivativeBacktestConfig.contract_specs: Mapping[str, ContractSpec] | None`
- Produces: `DerivativeBacktestConfig.min_rebalance_usdt: float = 0.0`
- Produces: `DerivativeBacktestConfig.normalize_isolated_margin: str = "none" | "rebalance" | "daily"`
- Produces: `DerivativeBacktestResult.margin_events`, `order_skips`
- Consumes: `ContractSpec.round_down_qty`, `ContractSpec.is_tradeable`

- [ ] Write failing tests for quantity flooring, below-minimum skip, daily margin add/remove, and equity conservation during margin normalization.
- [ ] Implement contract quantization in open/increase/reduce; risk-reducing full close always allowed.
- [ ] Implement daily margin normalization at 01:05, recording add/remove amount and cash transfer.
- [ ] Record `order_skips` with asset, action, requested/quantized size, reason.
- [ ] Run targeted tests.
- [ ] Commit `feat: add live-parity backtest execution model`.

### Task 4: data audit module and script

**Files:**
- Create: `src/atlas20/derivatives/data_audit.py`
- Create: `scripts/audit_derivatives_data.py`
- Modify: `Makefile`
- Test: `tests/test_derivatives_data_audit.py`

**Interfaces:**
- Produces: `audit_derivatives_data(raw_dir, panel_path, symbol_map_path, manifest_path) -> DataAuditReport`
- Produces: JSON/Markdown output with `hard_failures`, `warnings`, `checks`, `provenance`.
- Consumes: `load_mark_candles`, `load_bitget_funding`, `panel_completeness`, `contracts.json`, `symbol_map.csv`.

- [ ] Write failing tests for duplicate timestamps, future timestamps, invalid OHLC, missing last completed day, stale funding, ambiguous symbol map, and valid fixture.
- [ ] Implement panel, symbol map, mark, funding, contracts, cross-source and provenance checks.
- [ ] Add `make audit-data` target.
- [ ] Run `pytest tests/test_derivatives_data_audit.py -q`.
- [ ] Commit `feat: add derivatives data reliability audit`.

### Task 5: wire data audit and manifest provenance into live chain

**Files:**
- Modify: `scripts/run_derivatives_shadow.py`
- Modify: `scripts/execute_live_plan.py`
- Modify: `scripts/audit_live_track.py`
- Modify: `ops/run_derivatives_daily.sh`
- Modify: `Makefile`
- Test: `tests/test_execute_live_plan.py`
- Test: `tests/test_audit_live_track.py`

**Interfaces:**
- Consumes: `audit_derivatives_data`, manifest `data_fingerprint`, `execution_utc`.
- Produces: live executor fails if data audit or manifest fingerprint mismatches.

- [ ] Write failing tests for manifest execution clock mismatch and data hash mismatch.
- [ ] Add `data_fingerprint` and input hashes to manifest.
- [ ] Add `audit-data` before `execute_live_plan.py` in the daily wrapper.
- [ ] Add `audit-live` check for data audit status and manifest fingerprint.
- [ ] Run targeted tests.
- [ ] Commit `feat: gate live execution on data audit`.

### Task 6: generate 01:05 live-parity reports and compare

**Files:**
- Modify: `scripts/run_ls45_live_signal.py`
- Modify: `scripts/run_derivatives_shadow.py`
- Modify: `Makefile`
- Create: `reports/ls45_live_g125_legacy_0300/` (copy)
- Create: `reports/ls45_live_g125/` (new)
- Modify: `RESEARCH.md`
- Modify: `docs/operations/derivatives_live_runbook.md`
- Modify: `AGENTS.md`
- Modify: `README.md`

- [ ] Copy current `reports/ls45_live_g125` to `reports/ls45_live_g125_legacy_0300` before overwrite.
- [ ] Run LS45 full sample 2022-01-01..2026-09-21 with 01:05 ideal and live-parity.
- [ ] Run OOS 2026-09-22..latest with 01:05 live-parity using current contracts.
- [ ] Compare terminal multiple, Sharpe, MDD, turnover, fees, funding, liquidation, gross, quantization skips.
- [ ] Write `reports/ls45_live_g125_compare/report.md`.
- [ ] Update `RESEARCH.md` with a new section; do not delete old claims.
- [ ] Run `make audit-signal` and confirm 0 differences.
- [ ] Commit `research: align LS45 reports to 0105 live parity`.

### Task 7: full verification and live dry-run

**Files:**
- Modify: tests only if new regression discovered.

- [ ] Run `make test`.
- [ ] Run `make lint`.
- [ ] Run `make typecheck`.
- [ ] Run `make build`.
- [ ] Run `make audit-data`.
- [ ] Run `make audit-signal`.
- [ ] Run `make audit-live` with credentials.
- [ ] Run `scripts/execute_live_plan.py` dry-run with temporary state/journal/output.
- [ ] Confirm launchd/systemd schedules still fire at 09:05 Beijing and retries.
- [ ] Commit and push final fixes.
