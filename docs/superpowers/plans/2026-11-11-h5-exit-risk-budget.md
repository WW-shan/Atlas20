# H5 Exit Fixed-Risk Budget Plan

**Goal:** Test `PR2026-11-LS4-H5-EXIT-RISK05`, fixing each exit short at 2.5% NAV so a 20% stop risks 0.5% of account equity.

**Spec:** `docs/superpowers/specs/2026-11-11-h5-exit-risk-budget-design.md`

## Tasks

- [x] Add fixed per-asset exit-short weight support.
- [x] Add the risk-budget runner variant and structural tests.
- [x] Register the candidate before any formal run.
- [x] Run baseline and candidate at 20bps.
- [x] Run 2/50/100bps and 3x short-adverse funding.
- [x] Compute calendar, rolling, starts, multiple testing and episode attribution.
- [x] Write report + manifest and append ledger result.
- [x] Update `RESEARCH.md`, run full verification, commit and push.
