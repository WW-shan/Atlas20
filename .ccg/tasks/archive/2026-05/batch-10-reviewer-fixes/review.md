# Batch 10 Reviewer Fixes (Round 1 + Round 2 Info)

Builder commit: `c20b1d3 feat(api+ui): R10 batch 10 — R2 disk fallback + C5 verify + U10/U11 modals`

## Round-1 fixes

| Commit | Finding |
|---|---|
| `1bf306f` | fix(api): gate disk fallback on empty table |
| `234c906` | fix(api): expose queue favorites |
| `fc1e0cd` | fix(ui): label modal titles |

## Round-2 Info fixes

Per `.ccg/process/batch-execution-protocol.md` "Info 级别 finding 也要修" — all 2 remaining Opus Info findings followed up:

| Commit | Finding | Source |
|---|---|---|
| `b23fe9d` | docs(ui): document Dialog mouseDown rationale | Opus I1 |
| `3f03bec` | fix(ui): surface generateReport errors in NewReportModal | Opus I2 (+1 vitest case) |

## Verification at completion

- Backend pytest unchanged at 254 (Batch 10 was frontend-heavy)
- Frontend vitest 131 → 132 (+1 case for NewReportModal error path)
- TypeScript / lint clean
