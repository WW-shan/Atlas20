# H5 Exit Fixed-Risk Budget Plan

**Goal:** Test `PR2026-11-LS4-H5-EXIT-RISK05`, fixing each exit short at 2.5% NAV so a 20% stop risks 0.5% of account equity.

**Spec:** `docs/superpowers/specs/2026-11-11-h5-exit-risk-budget-design.md`

## Tasks

- [x] Add fixed per-asset exit-short weight support.
- [x] Add the risk-budget runner variant and structural tests.
- [ ] Register the candidate before any formal run.
- [ ] Run baseline and candidate at 20bps.
- [ ] Run 2/50/100bps and 3x short-adverse funding.
- [ ] Compute calendar, rolling, starts, multiple testing and episode attribution.
- [ ] Write report + manifest and append ledger result.
- [ ] Update `RESEARCH.md`, run full verification, commit and push.
