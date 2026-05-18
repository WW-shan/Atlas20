# Review Notes

Reviewed `docs/redesign/SPEC.md`, `docs/redesign/PLAN.md`, all six page plans plus `00-design-system.md`, and `apps/web/src/lib/api.ts`.

Primary issues found:
- Phase 1 uses `SectionHeader` before Phase 2 creates it.
- Page plans still contain stale paths/colors/signatures overridden by SPEC.
- Page2 lacks a run-detail data contract for the selected run equity workspace.
- Component/API contracts are missing for `QueryBoundary`, `PillButton`, `outline-dashed`, `SortKey`, and several actions.
- Tests do not cover every introduced action/mutation and do not map loading/error/empty per query.
