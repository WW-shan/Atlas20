VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
VENV_STAMP := $(VENV)/.installed

.PHONY: setup dev test test-fast lint typecheck build docker-build backup storage openapi load-test protect-logs clean record-capital-flow derivatives-live derivatives-live-data derivatives-ls45-signal derivatives-ls104-signal derivatives-refresh-ls104 derivatives-notify-ls104 derivatives-live-ls104 execution-plan-live-ls104 execute-plan-ls104 protect-live-ls104 reconcile-live-ls104 audit-data audit-data-chain audit-data-ls104 audit-market-cap-gaps audit-signal audit-signal-ls104 audit-symbols audit-symbols-ls104 audit-live audit-live-ls104 audit-accounting-ls104 audit-contract-specs-ls104 audit-funding-semantics-ls104 audit-funding-publication-boundary-ls104

$(PYTHON):
	python -m venv $(VENV)

$(VENV_STAMP): pyproject.toml $(PYTHON)
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -e ".[dev]"
	touch $(VENV_STAMP)

setup: $(VENV_STAMP)

dev: $(VENV_STAMP)
	PYTHONPATH=src $(PYTHON) -m uvicorn atlas20.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000

test: $(VENV_STAMP)
	$(PYTHON) -m pytest tests/ -q
	npm --prefix apps/web test -- --run

test-fast: $(VENV_STAMP)
	$(PYTHON) -m pytest tests/ -x -q --ff

lint: $(VENV_STAMP)
	$(PYTHON) -m ruff check src tests
	npm --prefix apps/web run lint

# typecheck mirrors CI's strict API mypy scope.
typecheck: $(VENV_STAMP)
	$(PYTHON) -m mypy --strict src/atlas20/api
	npm --prefix apps/web run typecheck

build:
	npm --prefix apps/web run build

docker-build:
	docker compose build

backup: $(VENV_STAMP)
	$(PYTHON) -m atlas20.api.backup

storage: $(VENV_STAMP)
	$(PYTHON) -m atlas20.api.storage

openapi: $(VENV_STAMP)
	$(PYTHON) -m atlas20.api.openapi

load-test: $(VENV_STAMP)
	$(PYTHON) scripts/load_test_api.py --rps 100 --duration-seconds 60 --p95-ms 200

# Refresh the CMC/Binance cache and rebuild the processed PIT panel.  The
# derivatives signal reads data/processed/panel_daily.csv, so this must run on
# every host that serves the daily broadcast (mirrors the macOS launchd job).
refresh-data: $(VENV_STAMP)
	$(PYTHON) scripts/download_data.py --config config/base.yaml
	$(PYTHON) scripts/build_datasets.py --config config/base.yaml

# Shared derivatives live chain.  The selected profile produces a frozen
# research wrapper from Bitget mark candles; it is never parameter-selected by
# this target.  Keep the raw directory stable so daily downloads append to one
# resumable cache and every live artifact points at the same identity.
DERIVATIVES_LIVE_RAW_DIR ?= data/raw/bitget_derivatives/merged_oos_20261112
DERIVATIVES_LIVE_MARK_WAIT_SECONDS ?= 180
DERIVATIVES_LIVE_MARK_POLL_SECONDS ?= 30
AUDIT_REQUIRED_LEVERAGE ?= 2.0
AUDIT_SYMBOL_OUT ?= reports/ls45_live_g125_live/venue_symbol_audit.json

derivatives-live-data: $(VENV_STAMP)
	$(PYTHON) scripts/download_bitget_derivatives_data.py \
		--output-dir $(DERIVATIVES_LIVE_RAW_DIR) \
		--start $(shell $(PYTHON) -c "import datetime;print((datetime.datetime.now(datetime.UTC)-datetime.timedelta(days=3)).date())") \
		--end $(shell $(PYTHON) -c "import datetime;print((datetime.datetime.now(datetime.UTC)+datetime.timedelta(days=1)).date())") \
		--types mark,market \
		--wait-for-live-mark-seconds $(DERIVATIVES_LIVE_MARK_WAIT_SECONDS) \
		--wait-for-live-mark-poll-seconds $(DERIVATIVES_LIVE_MARK_POLL_SECONDS) \
		--execution-utc 01:05

derivatives-ls45-signal: derivatives-live-data $(VENV_STAMP)
	$(PYTHON) scripts/run_ls45_live_signal.py

derivatives-live: derivatives-live-data derivatives-ls45-signal
	$(MAKE) audit-data
	$(MAKE) audit-data-chain
	$(MAKE) audit-symbols
	$(MAKE) audit-signal
	$(PYTHON) scripts/execute_live_plan.py --live --notify --require-isolated $(ARGS)

# LS104 is the owner-approved aggressive track.  It is deliberately a
# separate artifact/state family: LS45-G125 files are never overwritten.
LS104_SPEC ?= PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090
LS104_TARGETS ?= reports/ls45_live_g175/oos_targets.csv
LS104_MANIFEST ?= reports/ls45_live_g175/manifest.json
LS104_STATE ?= data/ls45_g175_execution_state.json
LS104_JOURNAL ?= reports/ls45_live_g175_live/journal.csv
LS104_AUDIT ?= reports/ls45_live_g175_live/audit.json
LS104_SIGNAL_EQUIVALENCE ?= reports/ls45_live_g175_live/signal_equivalence.json
LS104_KILL ?= data/ls45_g175_execution.KILL
LS104_LOCK ?= data/derivatives_execution.lock
LS104_PLAN_STATE ?= data/ls45_g175_plan_state.json
LS104_TELEGRAM_STATE ?= data/ls45_g175_telegram_state.json
LS104_BOOTSTRAP_ARG = $(if $(wildcard $(LS104_STATE)),,--bootstrap-track)
LS104_PRIOR_ORDER_REGISTRY ?= reports/ls45_live_g175_live/prior_track_order_registry.json


# Rebuild the frozen LS104 ledger without downloading.  When the UTC day has
# just rolled over and the panel/01:00 mark are not ready yet, an end-date pin
# is the last fully evaluated signal day; it lets the same target ledger be
# audited repeatedly while the data chain catches up.
LS104_SIGNAL_END_DATE ?= $(shell $(PYTHON) scripts/resolve_signal_end_date.py --panel data/processed/panel_daily.csv --raw-dir $(DERIVATIVES_LIVE_RAW_DIR) --execution-utc 01:05 2>/dev/null || true)

derivatives-ls104-signal: $(VENV_STAMP)
	$(PYTHON) scripts/run_ls45_live_signal.py --track ls104-g175-m090 --allow-final-provisional-fill $(if $(LS104_SIGNAL_END_DATE),--end-date $(LS104_SIGNAL_END_DATE))


# Intraday, non-trading refresh.  The daily executor is intentionally limited
# to its T+1 window; this target keeps marks/funding and the frozen LS104
# manifest fresh between executions without ever calling the executor.
derivatives-refresh-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/refresh_derivatives_data.py


derivatives-notify-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/send_derivatives_signal.py \
		--targets-file $(LS104_TARGETS) \
		--spec $(LS104_SPEC) \
		--state-file $(LS104_TELEGRAM_STATE) \
		--execution-state-file $(LS104_STATE) $(ARGS)


audit-data-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/audit_derivatives_data.py \
		--manifest $(LS104_MANIFEST) \
		--targets-file $(LS104_TARGETS) \
		--json-out reports/ls45_live_g175/data_audit.json \
		--markdown-out reports/ls45_live_g175/data_audit.md \
		--required-leverage 4.0 \
		--require-all-funding-fresh
	$(MAKE) audit-market-cap-gaps


audit-contract-specs-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/audit_contract_spec_snapshots.py


audit-funding-semantics-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/audit_bitget_funding_semantics.py


audit-funding-publication-boundary-ls104: $(VENV_STAMP)
	@test -n "$(FUNDING_SETTLEMENT)" || (echo "FUNDING_SETTLEMENT is required, e.g. FUNDING_SETTLEMENT=2026-11-16T16:00:00Z" >&2; exit 2)
	$(PYTHON) scripts/audit_bitget_funding_publication.py \
		--expected-settlement $(FUNDING_SETTLEMENT) \
		--json-out reports/ls45_live_g175/funding_publication_boundary_probe.json


audit-market-cap-gaps: $(VENV_STAMP)
	$(PYTHON) scripts/audit_market_cap_gaps.py \
		--config config/base.yaml \
		--panel data/processed/panel_daily.csv \
		--csv-out reports/ls45_live_g175/market_cap_gaps.csv \
		--json-out reports/ls45_live_g175/market_cap_gaps.json


audit-symbols-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/audit_venue_symbols.py \
		--required-leverage 4.0 \
		--out reports/ls45_live_g175_live/venue_symbol_audit.json


audit-signal-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/audit_signal_equivalence.py \
		--targets-file $(LS104_TARGETS) \
		--manifest-file $(LS104_MANIFEST) \
		--json-out $(LS104_SIGNAL_EQUIVALENCE) \
		--track ls104-g175-m090


audit-accounting-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/audit_derivatives_accounting.py \
		--output-dir reports/ls45_live_g175 \
		--raw-dir $(DERIVATIVES_LIVE_RAW_DIR) \
		--initial-capital 500 \
		--cost-bps 20 \
		--max-gross 1.75 \
		--json-out reports/ls45_live_g175/accounting_audit.json


audit-live-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/audit_live_track.py \
		--spec $(LS104_SPEC) \
		--targets-file $(LS104_TARGETS) \
		--manifest-file $(LS104_MANIFEST) \
		--state-file $(LS104_STATE) \
		--journal-file $(LS104_JOURNAL) \
		--prior-track-registry $(LS104_PRIOR_ORDER_REGISTRY) \
		--json-out $(LS104_AUDIT)


derivatives-live-ls104: derivatives-live-data derivatives-ls104-signal
	$(MAKE) audit-data-chain
	$(MAKE) audit-symbols AUDIT_REQUIRED_LEVERAGE=4.0 \
		AUDIT_SYMBOL_OUT=reports/ls45_live_g175_live/venue_symbol_audit.json
	$(MAKE) audit-data-ls104
	$(MAKE) audit-contract-specs-ls104
	$(MAKE) audit-signal-ls104
	$(PYTHON) scripts/execute_live_plan.py \
		--live --notify --require-isolated \
		--spec $(LS104_SPEC) \
		--targets-file $(LS104_TARGETS) \
		--manifest-file $(LS104_MANIFEST) \
		--state-file $(LS104_STATE) \
		--journal-file $(LS104_JOURNAL) \
		--json-out reports/ls45_live_g175_live/latest.json \
		--kill-switch $(LS104_KILL) \
		--lock-file $(LS104_LOCK) \
		--leverage 4.0 \
		--max-gross-multiple 1.75 \
		--max-margin-utilization 0.90 $(LS104_BOOTSTRAP_ARG) $(ARGS)

# Legacy L125 research refresher. The live chain above no longer calls these
# targets; they remain only for reproducing the previous research track.
# The start date has to roll: the downloader caches per window start, so a
# fixed start would mark the window complete once and then never extend the
# candles again (which silently froze the OOS clock on 2026-10-09).
derivatives-oos-data: $(VENV_STAMP)
	$(PYTHON) scripts/download_bitget_derivatives_data.py \
		--output-dir data/raw/bitget_derivatives/merged_oos_20261009 \
		--start $(shell $(PYTHON) -c "import datetime;print((datetime.datetime.now(datetime.UTC)-datetime.timedelta(days=3)).date())") \
		--end $(shell $(PYTHON) -c "import datetime;print((datetime.datetime.now(datetime.UTC)+datetime.timedelta(days=1)).date())") \
		--types mark

derivatives-oos: $(VENV_STAMP)
	$(PYTHON) scripts/run_derivatives_oos.py

derivatives-signal: $(VENV_STAMP)
	$(PYTHON) scripts/send_derivatives_signal.py --dry-run

# Live execution planning sized from the real balance (manual, dry by default).
# EQUITY=500 make execution-plan        -> plan from a manual equity number
# make execution-plan-live              -> read the Bitget UTA account, notify
execution-plan: $(VENV_STAMP)
	$(PYTHON) scripts/plan_live_execution.py --equity $(or $(EQUITY),1000)

execution-plan-live: $(VENV_STAMP)
	$(PYTHON) scripts/plan_live_execution.py \
		--live --notify \
		--execution-state-file data/ls45_g125_execution_state.json

# Current LS104 read-only plan and executor dry-run.  Keep the legacy targets
# above untouched for the LS45 fallback, but do not make an operator infer the
# LS104 paths/limits from defaults that intentionally still describe LS45.
execution-plan-live-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/plan_live_execution.py \
		--live --notify \
		--spec $(LS104_SPEC) \
		--targets-file $(LS104_TARGETS) \
		--manifest-file $(LS104_MANIFEST) \
		--state-file $(LS104_PLAN_STATE) \
		--execution-state-file $(LS104_STATE) \
		--leverage 4.0 \
		--max-gross-multiple 1.75 \
		--max-margin-utilization 0.90 \
		--cost-bps 20.0

execute-plan-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/execute_live_plan.py \
		--spec $(LS104_SPEC) \
		--targets-file $(LS104_TARGETS) \
		--manifest-file $(LS104_MANIFEST) \
		--state-file $(LS104_STATE) \
		--journal-file $(LS104_JOURNAL) \
		--kill-switch $(LS104_KILL) \
		--lock-file $(LS104_LOCK) \
		--leverage 4.0 \
		--max-gross-multiple 1.75 \
		--max-margin-utilization 0.90

protect-live-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/execute_live_plan.py \
		--live --notify --require-isolated --protect-only \
		--spec $(LS104_SPEC) \
		--targets-file $(LS104_TARGETS) \
		--manifest-file $(LS104_MANIFEST) \
		--state-file $(LS104_STATE) \
		--journal-file $(LS104_JOURNAL) \
		--json-out reports/ls45_live_g175_live/latest.json \
		--kill-switch $(LS104_KILL) \
		--lock-file $(LS104_LOCK) \
		--leverage 4.0 \
		--max-gross-multiple 1.75 \
		--max-margin-utilization 0.90 $(ARGS)

reconcile-live-ls104: $(VENV_STAMP)
	$(PYTHON) scripts/execute_live_plan.py \
		--live --notify --reconcile-only \
		--spec $(LS104_SPEC) \
		--state-file $(LS104_STATE) \
		--journal-file $(LS104_JOURNAL) \
		--json-out reports/ls45_live_g175_live/reconcile.json \
		--kill-switch $(LS104_KILL) \
		--lock-file $(LS104_LOCK) $(ARGS)

# Automated daily execution: reads the frozen book, sizes it from the real
# balance, places the orders, and reports the *venue's* fills/positions.
# Dry run (no orders) unless --live is passed.
execute-plan: $(VENV_STAMP)
	$(PYTHON) scripts/execute_live_plan.py

execute-plan-live: $(VENV_STAMP)
	$(PYTHON) scripts/execute_live_plan.py --live --notify --require-isolated $(ARGS)

# Record an external account transfer without polluting strategy PnL.
# Usage: make record-capital-flow AMOUNT=400 NOTE='deposit'
record-capital-flow: $(VENV_STAMP)
	@test -n "$(AMOUNT)" || (echo "AMOUNT is required: use AMOUNT=400 or AMOUNT=-100" >&2; exit 2)
	$(PYTHON) scripts/record_capital_flow.py --amount="$(AMOUNT)" --note="$(NOTE)"

# Read-only end-to-end reconciliation: account identities, ledger vs venue
# order history, book vs frozen target, and the selected profile's risk caps.
audit-live: $(VENV_STAMP)
	$(PYTHON) scripts/audit_live_track.py

# Read-only full-universe capability proof: every mapped CMC asset against
# Bitget's live v3 instruments, quotes, long/short order plans and flip plans.
audit-symbols: $(VENV_STAMP)
	$(PYTHON) scripts/audit_venue_symbols.py \
		--required-leverage $(AUDIT_REQUIRED_LEVERAGE) \
		--out $(AUDIT_SYMBOL_OUT)

# Fail-closed reliability audit for the CMC panel, symbol map, contracts,
# Bitget marks and funding. The daily wrapper runs this after the signal book
# is rebuilt and before the executor can place an order.
audit-data: $(VENV_STAMP)
	$(PYTHON) scripts/audit_derivatives_data.py

# Full provider-to-panel audit for the daily live chain.  The derivatives
# audit above checks the execution inputs; this target additionally proves the
# point-in-time universe, provider cross-checks, feed continuity and engine
# missing-return policy from the rebuilt canonical panel.
audit-data-chain: $(VENV_STAMP)
	$(PYTHON) scripts/audit_data_chain.py --config config/base.yaml

# Prove the live target book is the same computation as the reviewed
# backtest (rebuild both, compare every overlapping target event).
audit-signal: $(VENV_STAMP)
	$(PYTHON) scripts/audit_signal_equivalence.py

# macOS only: make the launchd logs append-only so cleanup tools cannot delete
# them. The com.atlas20.protect-live-logs agent reruns this at login and every
# five minutes; this target is for immediate application and troubleshooting.
protect-logs:
	/bin/sh ops/protect_live_logs.sh

derivatives-notify: $(VENV_STAMP)
	$(PYTHON) scripts/send_derivatives_signal.py

clean:
	rm -rf .pytest_cache .mypy_cache apps/web/node_modules apps/web/dist
