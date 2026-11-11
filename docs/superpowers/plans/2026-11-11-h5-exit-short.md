# H5 Exit-Short Research Plan

**Goal:** Evaluate `PR2026-11-LS3-H5-EXIT-SHORT21` with H5's unused gross budget, a fixed 21-day exit short and a next-tick gross guard.

**Spec:** `docs/superpowers/specs/2026-11-11-h5-exit-short-design.md`

## Task 1: Implementation

- [x] Add failing tests for H5 exit scheduling and cash-budgeted shorts.
- [x] Implement exit scheduling, early re-entry exit and unused-gross allocation.
- [x] Add failing tests for the hourly hard gross guard.
- [x] Implement next-tick proportional deleveraging with `reason=gross_guard`.
- [x] Add the research runner and focused tests.
- [x] Run focused tests, Ruff and mypy.

## Task 2: Registration

- [ ] Append one registration row before viewing formal engine results.
- [ ] Freeze the 21-day horizon, 20% stop, 0.95 target and 1.00 hard gross.
- [ ] Commit registration.

## Task 3: Formal runs

- [ ] Baseline and candidate at 20bps.
- [ ] Baseline and candidate at 2/50/100bps.
- [ ] 3x short-adverse funding.
- [ ] Commit raw results.

## Task 4: Robustness and close-out

- [ ] Yearly, best-year removal and 365-day rolling worst.
- [ ] 12 engine monthly starts with at least 365 days remaining.
- [ ] PBO, Reality Check and DSR at family, Top20/2022 and all-project scopes.
- [ ] Exit-short episode attribution.
- [ ] Report + manifest.
- [ ] Ledger result row.
- [ ] Update `RESEARCH.md`.
- [ ] Full tests, lint, typecheck, diff check, commit and push.
