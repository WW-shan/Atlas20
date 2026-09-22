# Phase-Sensitive Result Warning

The 25.87x @2bps and 22.44x @20bps figures in this report are tied to the
exact 2022-01-01 rebalance phase.

A September 2026 audit shifted the same 21-day rule by 0-20 days while keeping
every other rule unchanged:

- 20bps median across the 21 phases: 3.94x
- 20bps worst phase: 0.61x
- 20bps best phase: 22.44x (this report)
- fully staggered 21-tranche implementation: 5.51x, Sharpe 1.11, MDD -34.6%

The fully staggered implementation is invariant to the starting phase.  The
figures in this directory should therefore be treated as a research upper tail,
not as the production expectation.

A second audit isolates the inherited 11-day/two-day BTC gate.  Even the
phase-invariant 5.51x basket is a local parameter spike: 10-day and 14-day
trailing lookbacks return 3.05x and 1.98x, while one-day and five-day
confirmation settings of the same gate return 2.20x and 2.30x.  The gate must
be replaced or independently validated before this strategy can be considered
production ready.

See:

- `docs/research/strategy_evidence_audit.md`
- `reports/strategy_evidence_audit_2022/`
- `reports/decision_point_ablation_2022/`
