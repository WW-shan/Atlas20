# Batch 19 Carry-over — Final Cross-Validation Matrix

**Branch:** `redesign/r3-premium`
**Final HEAD:** `d8c3c56` (r2 doc patch on top of r2 critical fix)
**Termination criterion:** Both reviewers (Opus 4.7 self-review + codex) return zero in-scope findings.

## Origin

B18 reached zero in-scope findings under the dual-reviewer protocol. B18's final-cross-validation-matrix.md called out 3 carry-over items "Still deferred to B19+":
1. Worker queue-loop healthcheck (docker-compose only probed HTTP listener)
2. `reporting/report.py:465` hardcoded "Rebalancing tested: monthly and biweekly."
3. `yearly_return_table` "Unnamed: 0" pandas index artifact in markdown table

## Round-by-round outcomes

| Round | Codex | Findings | Action |
| --- | --- | --- | --- |
| r1 | 82/100 REQUEST_CHANGES | 1 Critical: queue-loop gauge stops updating during long backtests (main loop blocked on subprocess.communicate for up to run_timeout_seconds) → 30s docker healthcheck would falsely kill a healthy worker mid-run. | r2 fixer commit `6901977` |
| **r2** | **96/100 APPROVE** | **0 in-scope** ("Ready to archive"). 1 out-of-scope: worker.md only attributed gauge tick to main poll loop, should also mention heartbeat-thread path | r2 doc patch `d8c3c56` |

Opus self-review concurrent: r1 95/100 APPROVE; r2 95/100 APPROVE.

## Commits landed (B19 cycle, ordered)

1. `0a461d5` fix(reporting): report scope reflects actual cadences; yearly_return_table names its year index
2. `6dbcdae` feat(api): worker queue-loop liveness gauge + docker healthcheck upgrade
3. `3f49bdf` test(api): cover worker poll-tick gauge invocation
4. `6901977` fix(api): r2 — heartbeat thread also stamps worker liveness gauge during in-flight runs (codex r1 Critical fix)
5. `d8c3c56` docs(infra): r2 — worker.md mentions both gauge-tick paths and tuning interaction (codex r2 out-of-scope)

## What this batch fixed

### 3 carry-overs from B18

- **#1 Queue-loop healthcheck**: Added `atlas20_worker_last_poll_timestamp_seconds` Gauge with `multiprocess_mode="max"`. Two tick paths: main poll loop (idle worker) and heartbeat thread (in-flight run). Docker healthcheck switched to Python one-liner that scrapes /metrics, extracts the gauge via `re.M`/`\S+` regex (handles scientific notation), fails if older than 30s or absent. Live verified: gauge age 0.57s during smoke. (6dbcdae + 6901977)
- **#2 Hardcoded "Rebalancing tested" string**: derived from `config.strategies.{momentum,sector}_frequencies` union. Live verified: Weekly run now reports `Rebalancing tested: weekly.` in report scope. (0a461d5)
- **#3 yearly_return_table "Unnamed: 0"**: set `frame.index.name = "year"`. Live verified: markdown table header now `| year | BTC_BH... |` and `yearly_returns.csv` starts with `year,...`. (0a461d5)

## Test verification at HEAD

- `PYTHONPATH=src python -m pytest tests/ -q` → **367 passed, 2 skipped** (was 366 at B18 → +3 regression tests: cadence text, poll-tick callback, heartbeat-tick callback)
- `python scripts/check_repo_health.py` → exit 0

## Live verification

Weekly backtest btk_0012 (window 2024-01-01..2024-06-30, topN=10):
- Completed in 16s, all metrics non-zero
- Heartbeat gauge age 0.57s at completion
- `reports/app_runs/btk_0012/digest.md` scope: `Rebalancing tested: weekly.` (was `monthly and biweekly` hardcoded pre-B19)
- `reports/app_runs/btk_0012/yearly_returns.csv` first line: `year,BTC_BH__always_on,...`
- Markdown yearly table header: `| year | BTC_BH__always_on | ... |` (was `| Unnamed: 0 | ... |` pre-B19)

## Still deferred to B20+ (no known items)

After B19 there is no outstanding finding from any prior batch's archive matrix, no codex out-of-scope item that affects correctness, and no pre-existing bug observed during live smoke.

## Observed asymmetry

In B17 codex caught 5 doc-level items Opus missed; Opus caught 2 Criticals codex missed. In B18 codex caught BOTH critical regressions Claude missed. In B19 codex caught **another** Critical (long-run gauge staleness) that:
- Claude's live smoke completed in 16s (well under 30s window) so the issue never surfaced
- Test suite had no in-flight backtest longer than 30s
- The bug would have manifested in production on any backtest >= 30s

Lesson: smoke depth matters. The B19 gauge added a new failure mode (false-positive kills) that's invisible to short tests. Cross-validation with codex's read-of-code paranoia is what caught it.
