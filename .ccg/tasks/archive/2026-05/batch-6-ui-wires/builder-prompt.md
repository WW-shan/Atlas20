You are the codex builder for Atlas20 Batch 6 (frontend UI wiring).

Read the brief at `.ccg/tasks/batch-6-ui-wires/brief.md` and implement
EVERYTHING in the "Scope" section.

Hard requirements:
1. Frontend-only. NO backend changes. NO schema changes.
2. Read each affected `.tsx` file before editing — verify exact prop
   signatures of `<Skeleton>`, `<EmptyState>`, `<ErrorBanner>`, `<Button>`.
3. Tests in Vitest + Testing Library. Mock `lib/api` exports per test.
4. Final checks (all must pass):
   - `cd apps/web && npm run test -- --run`
   - `cd apps/web && npm run typecheck`
   - `cd apps/web && npm run lint`
   - `python -m pytest tests/ -q` (113 passed, no backend regression)
5. Apply your own internal review BEFORE the final commit (use the same
   pattern from Batch 4/5).
6. Stage and commit with message:
   `feat(ui): R6 batch 6 — wire Loading/Error/Empty states across remaining tabs`

Report format:
- ✅/❌ PASS or FAIL
- Files changed
- Frontend test count delta
- Backend pytest still 113
- typecheck + lint exit codes
- Any deviations
- Final commit hash
