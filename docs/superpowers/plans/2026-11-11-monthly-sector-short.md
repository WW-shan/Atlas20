# Monthly Sector Short Research Plan

**Goal:** Evaluate the pre-registered `PR2026-11-LS2-H5-MONTHLY-SECTOR` candidate with strict two-sided gross accounting and no live changes.

**Spec:** `docs/superpowers/specs/2026-11-11-monthly-sector-short-design.md`

## Task 1: Add total-gross composition and runner

- [x] Add failing tests for two-sided gross accounting.
- [x] Implement total-gross composition with a pre-net sleeve audit.
- [x] Add failing structural tests for the monthly sector runner.
- [x] Implement the runner with joint long+short scaling, Bitget mark, funding proxy and 20% short stop.
- [x] Run focused tests, Ruff and mypy.

## Task 2: Register before running

- [ ] Append exactly one registration row for `PR2026-11-LS2-H5-MONTHLY-SECTOR`.
- [ ] Freeze costs 2/20/50/100, target total gross 0.95 and hard total gross 1.00.
- [ ] Commit the registration before viewing formal results.

## Task 3: Run formal tests

- [ ] Run H5 baseline at 20bps.
- [ ] Run LS2 candidate at 20bps.
- [ ] Run candidate and baseline at 2/50/100bps.
- [ ] Run 3x short-adverse funding.
- [ ] Commit raw results.

## Task 4: Robustness and multiple testing

- [ ] Compute yearly returns, best-year removal and 365-day rolling worst.
- [ ] Run 12 engine-level monthly starts with at least 365 days remaining.
- [ ] Compute PBO, White Reality Check and DSR at family, Top20/2022 and all-project scopes.
- [ ] Attribute short episodes and target gross.
- [ ] Write report and manifest.
- [ ] Append the evaluated result row without changing the registration.
- [ ] Update `RESEARCH.md`.
- [ ] Run full tests, lint, typecheck and `git diff --check`.
- [ ] Commit and push.
