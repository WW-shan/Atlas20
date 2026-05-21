## Summary

<!-- One paragraph: what this PR changes and why. Mention the user-visible
     effect, not just the diff. If it's a bug fix, point at the failure mode. -->

## Type of change

- [ ] Bug fix (non-breaking change that fixes correctness or behavior)
- [ ] New feature (non-breaking change that adds capability)
- [ ] Breaking change (existing API, schema, or contract changes)
- [ ] Refactor / cleanup (no behavior change)
- [ ] Documentation / build / CI

## Test plan

<!-- Checklist of what was verified before requesting review. -->

- [ ] `PYTHONPATH=src python -m pytest tests/ -q` passes locally
- [ ] `npm --prefix apps/web test` passes locally
- [ ] `npm --prefix apps/web run typecheck` clean
- [ ] Live smoke (if UI/backend touched): worker + API + web stack started and the affected surface manually verified
- [ ] No new hardcoded fake/mock values displayed to the user
- [ ] Updated docs if observability metric / endpoint contract changed

## Migration / runtime impact

<!-- Skip if none. Note any new env var, DB migration, config change, or
     compatibility break operators need to know about. -->

## Linked issues / batches

<!-- Reference any related ccg batch archive (e.g. B22 final closure) or
     GitHub issue. -->
