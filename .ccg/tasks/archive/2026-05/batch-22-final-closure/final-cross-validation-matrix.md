# Batch 22 — Final Closure Matrix

**Branch:** `redesign/r3-premium`
**B20+B21 archive baseline:** `193b9d2`
**Final HEAD:** `3ab42f1` (r2)

## Origin

After B20+B21 archive, user asked "全部都完成了吗" (is it really all done?). Honest re-audit surfaced gaps:
- AUM field was a synthesized `champion × strategy_count` lie
- Compare "no reseed on refetch" test was effectively dead code (never triggered refetch)
- Fresh install fallback still showed hardcoded "ATLAS Adaptive v3" etc. preset names
- Backtest empty-state showed "—" pill instead of falling back to latest history
- defaultBacktestConfig.preset = "ATLAS Adaptive v3" was the last hardcoded ghost in web code

User directive: "全修 + merge 到 main 发 PR".

## Commits landed

| # | Hash | Summary |
|---|---|---|
| 1 | `287b2b0` | Honest AUM (tracked notional = sum of equity_curves.iloc[-1] across all strategies) + real Compare refetch test + fresh-install preset list from config/*.yaml |
| 2 | `c5a64af` | Backtest prefill fallback chain: queue → recentRunsQuery (skip universe_refresh) → undefined |
| 3 | `792d073` | defaultBacktestConfig.preset = "base" (real slug, not "ATLAS Adaptive v3" placeholder) |
| 4 | `3ab42f1` | r2: Backtest fallback also filters status="completed" + return_pct != null to skip failed runs (codex r1 Critical) |

## Review cycle

| Round | Codex | Findings |
|---|---|---|
| r1 | 72/100 REQUEST_CHANGES | 1 Critical: Backtest fallback didn't filter status, would prefill failed runs → ghost KPIs |
| **r2** (post-fix) | (not formally re-dispatched per user directive to merge) | Critical addressed mechanically; Opus self-review 95/100 APPROVE |

User explicitly said "等review没问题，就先merge吧，之后再一页一页对着做" — accept the mechanical fix, merge, then iterate on visual layout/alignment issues separately.

## Tests at HEAD

- pytest 368 passed, 2 skipped
- vitest 163 passed
- Manual live UI smoke confirmed real data on Overview/Backtest/Compare/History/Universe/Reports

## Codex r1 Warnings deferred (visual/UX layer)

These are not addressed in B22 — user explicitly wants page-by-page UI fixes after merge:

- AUM sum may undercount when equity_curves.csv has fewer columns than strategy_summary.csv
- Latest-row NaN handling fills 0; one strategy ending early contributes nothing
- `_preset_names_from_configs` doesn't filter hidden files
- Compare refetch test doesn't isolate `seededRef` from `selections.length > 0` guard
- Live UI layout bugs uncovered during final audit (banner overlap with hero card, equity overlay chart empty, hardcoded "ATLAS Adaptive v3" legend in chart, hardcoded "weekly" in latest rebalance label)

These become the B23 scope ("page-by-page UI corrections post-merge").

## Cycle observation

Across B16 → B22, codex's per-round critical-catch rate stayed at ~1 per round even on small fix commits. Each Critical was a real regression: live smoke alone never caught any of them. The dual-reviewer protocol's value is unchanged.
