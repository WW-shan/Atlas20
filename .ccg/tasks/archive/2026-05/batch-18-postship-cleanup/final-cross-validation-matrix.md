# Batch 18 Post-Ship Cleanup — Final Cross-Validation Matrix

**Branch:** `redesign/r3-premium`
**Final HEAD:** `71bac86` (r3)
**Termination criterion:** Both reviewers (Opus 4.7 self-review + codex) return zero in-scope findings.

## Origin

B17 reached zero in-scope findings under the dual-reviewer protocol, but live local-practice smoke (Claude + codex independent passes) surfaced 3 pre-existing bugs outside B17 scope plus 4 deferred Info findings flagged in the B17 archive matrix. User directive: 全清.

## Round-by-round outcomes

| Round | Codex | Findings | Action |
| --- | --- | --- | --- |
| r1 | 69/100 REQUEST_CHANGES | 1 Critical: hardcoded `BTC_BH/ETH_BH/TOP20_EQ` `frequency="monthly"` would crash Weekly/Biweekly after `6e14595` dropped non-chosen keys from the lookup table. | r2 fixer commits `0b87942` + `ac58662` |
| r2 | 76/100 REQUEST_CHANGES | 1 Critical: `dd3bfba` widened panel by `min_history_days` but the engine ran over the full returns index → CAGR/sharpe/yearly returns diluted by buffer flat days. 1 Warning: `0b87942` stored all 3 cadences in lookup table so pipeline did wasted universe work. | r3 fixer commits `2c1b1c7` + `71bac86` |
| **r3** | **100/100 APPROVE** | **0 in-scope** ("Ready to archive") | **— ship —** |

Opus self-review concurrent: r1 (not formally scored, found shadow-test caplog logger drift); r2 96/100 APPROVE; r3 95/100 APPROVE.

## Commits landed (B18 cycle, ordered)

1. `de2688e` chore: gitignore runtime artifacts under data/
2. `6e14595` fix(api): constrain strategy frequencies to chosen rebalance cadence (biweekly int parse crash)
3. `dd3bfba` fix(data): extend processed panel by min_history_days before backtest start (universe filter "No eligible assets")
4. `7db0865` docs(infra): fix worker.md PID-recovery wording + tick ROADMAP Phase O
5. `3dbdfac` refactor(api): extract shadow-install check to standalone module
6. `c1ebe3c` test(api): real run_one subprocess multiproc integration test
7. `0b87942` fix(api): r2 — preserve full frequency lookup table for hardcoded benchmark strategies (Critical from codex r1)
8. `ac58662` test(api): r2 — shadow-install tests target install_check logger; gitignore WAL sidecars
9. `2c1b1c7` fix(data): r3 — backtest runs only on [start,end] window, not on history buffer (Critical from codex r2)
10. `71bac86` perf(api): r3 — minimize frequency lookup table to cadences actually used (Warning from codex r2)

## What this batch fixed

### Real bugs uncovered in B17 live smoke

- **biweekly int parse crash**: `config_adapter` only constrained `rebalancing.frequencies` to chosen cadence; engine still iterated `strategies.momentum_frequencies = ["monthly", "biweekly"]` and crashed `int("biweekly")` in calendar.py for cadences whose YAML preset still listed biweekly. (#6e14595 → #0b87942 → #71bac86)
- **Universe eligibility "No eligible assets"**: processor truncated panel to `[start, end]` so `history_days = 0` at backtest start; `min_history_days = 90` filter rejected everything. (#dd3bfba)
- **Backtest metrics dilution**: above pre-buffer leaked into `run_backtest` daily_returns, diluting Sharpe by ~22% in our live test. (#2c1b1c7)
- **mojibake**: misdiagnosed during B17 smoke — server emits correct UTF-8; only Windows cp936 terminal mis-decodes. No fix needed.

### B17 deferred Info

- worker.md:35 PID-recovery wording (#7db0865)
- ROADMAP.md Phase O O1-O5 ticked (#7db0865)
- Worker dragged in `app.py`'s FastAPI/middleware/routes for one 30-line filesystem check → extracted to `install_check` (#3dbdfac)
- Multiproc test used `python -c` instead of real `run_one` → added real subprocess integration test (#c1ebe3c)

## Test verification at HEAD

- `PYTHONPATH=src python -m pytest tests/ -q` → **364 passed, 2 skipped** (was 361 at B17 ship → +3 new regression tests)
- `python scripts/check_repo_health.py` → exit 0

## Live verification

Same 2024-01-01..2024-06-30 Monthly topN=10 config:
- `btk_0007` (post-`dd3bfba`, pre-`2c1b1c7`): return=0.4715, **sharpe=1.467 (DILUTED)**, max_dd=-0.203
- `btk_0010` (post-`2c1b1c7`): return=0.4715, **sharpe=1.796 (CORRECT)**, max_dd=-0.203
- `btk_0011` (post-`71bac86`): identical to btk_0010

Weekly + Biweekly cadences both completed without `int("biweekly")` / "Unsupported rebalance frequency: monthly=monthly" crashes after r2.

## Still deferred to B19+

- Healthcheck queue-loop probe: docker-compose worker healthcheck still only `curl /metrics`; a queue heartbeat gauge + script that checks recency would catch frozen queue loops without HTTP listener failures
- Report header "Rebalancing tested: monthly and biweekly." is hardcoded in `reporting/report.py:465` despite API cadence overrides
- yearly_return_table column "Unnamed: 0" cosmetic artifact from pandas index export
- `__main__.py` env-handling concern from B17 archive matrix was a misread; no real issue

## Observed asymmetry vs B17

In B17, codex's paranoia mode surfaced 5 issues Opus missed; Opus caught 2 Criticals codex missed. In B18, **codex caught BOTH critical regressions Claude missed** (r1 benchmark crash and r2 metric dilution). Live smoke was insufficient because Claude only ran Monthly initially — the cadence that happened not to expose either critical. Lesson: cross-cadence smoke required for adapter changes; sharpe/CAGR comparison vs same-window pre-fix run is the smoking gun for buffer leakage.
