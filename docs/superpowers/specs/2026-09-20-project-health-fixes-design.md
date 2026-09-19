# Project Health Fixes Design

## Goal

Resolve the concrete repository health issues identified during the project
review without expanding into architectural refactoring.

## Scope

### 1. Frontend dependency security

- Upgrade the direct `echarts` dependency from the vulnerable 5.x line to a
  supported fixed release.
- Apply non-breaking lockfile updates for transitive security fixes where the
  current major versions allow them.
- Do not use `npm audit fix --force` to introduce unrelated breaking upgrades.
- Verify the result with frontend tests, typecheck, production build, and
  `npm audit`.

### 2. Report snapshot consistency

- Treat `reports/latest/manifest.json` as the integrity manifest for the
  checked-in `reports/latest` snapshot.
- Add a regression test that verifies every manifest artifact exists and that
  its byte size and SHA-256 digest match the manifest.
- Add a regression test that verifies the README "Current Included Snapshot"
  metrics match `reports/latest/strategy_summary.csv`.
- Rebuild the manifest from the current snapshot and update README values.

### 3. Verification

- Run the affected Python and frontend tests.
- Run Ruff, mypy, TypeScript typecheck, production build, and OpenAPI drift
  checks.
- Re-run Python and frontend dependency audits.
- Report any residual advisory that cannot be removed without a breaking
  ecosystem upgrade.

## Non-Goals

- Refactoring the API service layer.
- Replacing SQLite with PostgreSQL or an external queue.
- Expanding strict mypy coverage beyond the existing API scope.
- Changing public API contracts or research methodology.

## Acceptance Criteria

- `npm audit --audit-level=moderate` reports no unresolved vulnerability that
  can be fixed within the current supported dependency lines.
- All 38 checked-in `reports/latest` artifacts match the manifest.
- README snapshot metrics match the checked-in strategy summary.
- Existing Python and frontend test suites remain green.
- The new consistency checks fail if a snapshot file or documented metric
  drifts in the future.
