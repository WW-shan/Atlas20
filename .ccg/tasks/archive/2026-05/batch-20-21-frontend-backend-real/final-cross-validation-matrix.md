# Batches 20 + 21 — Final Cross-Validation Matrix (Frontend ↔ Backend Real-Data Wiring)

**Branch:** `redesign/r3-premium`
**B19 baseline:** `78de344` (archive)
**Final HEAD:** `d29768b` (r3)
**Termination criterion:** Both reviewers (Opus 4.7 self-review + codex) return zero in-scope Critical findings.

## Origin

User directive: "全部都正常能用" (everything must actually work). After 4 prior batches of backend hardening (B16-B19), a live Playwright-driven full-stack UI audit found that **multiple frontend surfaces displayed hardcoded fake values despite the backend payload containing real data**:

- Overview hero title was literal string "ATLAS Adaptive v3"; real `champion.strategy` was `ETH_BH__bull_only`
- Backtest preset dropdown hardcoded 4 fake names; real `/api/options` returns 30
- Backtest default `prefillRunId` was literal `"btk_0142"` that 404s in any real DB
- Compare initial selections hardcoded labels that lied (backend alias map silently resolved them)
- Overview `aum/strategies/regime/rebalance` returned `mock_data.fallback_overview` (marked `TODO(P2): replace`)
- `run_one` wrote `reports/latest.txt` with `.tmp` suffix (pipeline ran before publish-rename), so `/api/compare` fell back to mock even after a real run

## Round-by-round outcomes

| Round | Codex | Findings | Action |
| --- | --- | --- | --- |
| r1 (audit triage) | — | 5 hardcoded surfaces + 1 backend `latest.txt` bug + 4 mock Overview fields | B20 (5853dc8) + B21 P1+P2+P3 (0a8b08d) + B21 P4 (4ddc8ea) |
| r2 | 66/100 REQUEST_CHANGES | 2 Critical: Compare seeding fired on `initialData` fallback (ignored real /api/options); resolveCompareId slugified real preset names (backend rejected) | B21 r2 (61964b0) |
| r3 (post-fix) | 86/100 APPROVE | 0 Critical. 2 Warnings: tests bypassed cold-load via __TEST_DEFAULT_SELECTIONS prop; regime missed `data/processed/regime_frame.csv` root path | B21 r3 (d29768b) addressed both |
| **r4 (final)** | **93/100 APPROVE** | **0 in-scope** ("Ready to archive") | **— ship —** |

Opus self-review concurrent: r1 implicit during audit; r2 94/100 APPROVE; r3 95/100 APPROVE.

## Commits landed (B20+B21 cycle, ordered)

1. `5853dc8` fix(web): batch 20 — Overview champion title + Backtest preset dropdown use real backend data
2. `0a8b08d` fix(api,web): batch 21 — three UI/backend wiring closures (latest.txt pointer + backtest prefill + compare defaults)
3. `4ddc8ea` fix(api): batch 21 P4 — Overview aum/strategies/regime/rebalance now derived from real artifacts
4. `61964b0` fix(web): batch 21 r2 — Compare seeding waits for real /api/options data + preserves real strategy names
5. `d29768b` fix(api,web): batch 21 r3 — Overview regime checks root processed/ too + direct Compare seed regression tests

## What this batch fixed (closure on user's "全部都正常能用" directive)

### Frontend surfaces now show real backend data

- **Overview hero title**: `champion.strategy` (e.g. "ETH_BH__bull_only") + real `window_start → window_end`
- **Backtest preset dropdown**: 31 entries from `/api/options.presets` (30 real + 1 hydrated preserved)
- **Backtest prefillRunId**: `queue.data?.[0]?.run_id` fallback chain; empty state when no runs
- **Compare default chips**: seeded once from real `/api/options.presets` after first network roundtrip; user edits never clobbered by background refetches

### Backend real-data adapters

- **run_one.py**: `_write_latest_pointer(final_dir)` AFTER `_publish_report_dir` so `/api/compare` sees the FINAL report path
- **overview.py**: 4 new builders (`_build_strategies_breakdown`, `_build_regime`, `_compute_rebalance_swaps`, `_build_aum`) replace the `TODO(P2)` mock-data dispatcher. All Overview sub-payloads now derive from `strategy_summary.csv` / `selection_history.csv` / `regime_frame.csv` / champion equity
- **regime lookup**: globs `data/processed/<preset>/regime_frame.csv` AND root-level `data/processed/regime_frame.csv`; selects by `frame.index.max()` not `iloc[-1]` so unsorted CSVs work correctly

### Test isolation

- `test_generate_report_stub.py` fixture: monkeypatched `ATLAS20_REPORT_ROOT` and `ATLAS20_DATA_ROOT` but missed `ATLAS20_DB_URL`, leaking dev sqlite state. Added DB URL override.

## Test verification at HEAD

- `PYTHONPATH=src python -m pytest tests/ -q` → **367 passed, 2 skipped**
- `npm --prefix apps/web test` → **163 passed** (up from 161; +2 direct cold-load seeding regression tests)
- `scripts/check_repo_health.py` → exit 0

## Live verification

Playwright-driven UI audit against running backend (worker + uvicorn + vite dev):

| Surface | Real data observed |
|---|---|
| Overview hero | "ETH_BH__bull_only" champion title; real window 2021-01-01 → 2026-04-21 |
| Overview strategies | 5 real families (Momentum Rotation 6, Sector Rotation 6, BTC Benchmark 2, ETH Benchmark 2, Equal Weight 2) |
| Overview regime | RISK-OFF from real `regime_frame.csv`; model = "bull AND btc>MA200 AND mcap>MA200" |
| Overview rebalance | Real swaps from selection_history: BINANCECOIN→BITCOIN, BITCOIN-CASH→ETHEREUM, SHIBA-INU→SOLANA |
| Backtest preset dropdown | 31 entries (ETH_BH__bull_only, BTC_BH__always_on, TOP20_MOM_*, TOP20_SECTOR_*) |
| Backtest fresh run E2E | btk_0014 completed in ~10s; latest.txt pointed at `app_runs/btk_0014` (no .tmp) |
| Compare /api/compare | 180 real equity points after fresh run; overlap.symbols had real strategy names |
| History tab | All 14 real runs with real metrics (47.15% return, 1.80 sharpe, etc.) |
| Universe tab | 20 real tokens with real date ranges |
| Reports tab | Real generated digest.md reports |

## Observed asymmetry (the codex paranoia pattern continued)

Across r1 → r3, **codex caught 4 issues Claude's live UI audit missed**:
- r2 C1: Compare seeding fired on initialData fallback (visible only if you trace useQuery semantics)
- r2 C2: resolveCompareId slugified real preset names (visible only if you trace through to backend resolver)
- r2 W1: tests didn't directly assert cold-load behavior
- r2 W2: regime missed root-level regime_frame.csv

Claude's live audit caught the surface-level lies (hardcoded "ATLAS Adaptive v3", hardcoded preset list, etc.) but missed the deeper "seeding fires on placeholder data" and "slugification breaks backend lookup" semantic issues. The dual-reviewer protocol caught both classes.

## Still deferred (none)

No outstanding finding from any prior batch's archive matrix remains. No codex out-of-scope item affects correctness. No pre-existing bug observed during live full-stack audit. UI surfaces all show real backend data or honest empty state. End-to-end backtest → report → compare flow verified.
