# Review: batch 6 UI wires

Target: `a4238fd` (`feat(ui): R6 batch 6 — wire Loading/Error/Empty states across remaining tabs`)

Score: 94/100

Critical: none

Warning:
- Fixed in `dcb1d8d`: history favorite controls only disabled the clicked row while the shared favorite mutation/refetch was active; other visible star buttons could still look actionable.
- Fixed in `e26d7a4`: report download actions did not disable while download requests were pending, allowing repeat clicks on `DOWNLOAD ALL` and per-card downloads.

Info:
- U4, U5, U7, U9, and U12 loading/error/empty branches are present after fixes.
- Error states use `role="alert"` and loading/empty states use `role="status"`/`aria-busy` through shared components; no custom focus handoff was added.
- Tests are mostly user-visible role/text queries; skeleton-only assertions still use `data-testid`, matching the brief examples.
- External CCG wrapper review was unavailable because `$HOME/.claude/bin/codeagent-wrapper` is not present in this workspace.

Verification:
- `cd apps/web && npm run test -- --run`: 10 files, 120 tests passed.
- `cd apps/web && npm run typecheck`: passed.
- `cd apps/web && npm run lint`: passed.
- `python -m pytest tests/ -q`: 113 passed.
