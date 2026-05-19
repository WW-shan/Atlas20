# Batch 6 — Frontend UI wires (U4/U5/U7/U9/U12)

## Goal

Each tab currently relies on `initialData=fallback*` from TanStack Query so
it always has SOMETHING to render. That hides backend outages and slow loads
from the user. Add proper Loading / Error / Empty branches to the remaining
tabs (U6 Compare + U8 Universe done in prior batches).

Frontend-only. No backend changes. No schema changes.

## Scope

### U4 — `apps/web/src/pages/ResearchConsolePage.tsx`

Page-level loading + error orchestration. If the first `overviewQuery` is
loading (no `initialData` produces data fast enough) show a single full-page
`<Skeleton>` or a centered loader. If it errors, show `<ErrorBanner>`.

Keep tab switching responsive (don't block other tabs' independent queries).

### U5 — `apps/web/src/features/backtest/BacktestStudioTab.tsx`

Already partially handles `refresh.isPending`. Add:
- `detailQuery.isLoading` → render `<Skeleton variant="card">` placeholders
  for the form pre-fill section
- `detailQuery.isError` → `<ErrorBanner>` with retry button calling `refetch()`
- `queueQuery.isLoading` / `isError` separately handled in queue list area
- "Run" button disabled while `mutation.isPending`

### U7 — `apps/web/src/features/history/RunHistoryTab.tsx`

- `listQuery.isLoading` → table skeleton (5 skeleton rows)
- `listQuery.isError` → `<ErrorBanner>` above table with retry
- `listQuery.data.items.length === 0 && !isLoading` → `<EmptyState>` with
  copy "No runs match these filters" + clear-filters button if any filter
  is active; otherwise "No backtests yet"
- Filter chips disabled while loading

### U9 — `apps/web/src/features/reports/ReportsExportsTab.tsx`

- `featuredQuery.isLoading` → small spinner inside FeaturedDigestCard
- `featuredQuery.isError` → ErrorBanner inside card; download buttons disabled
- `archiveQuery.isLoading` → skeleton table rows (5)
- `archiveQuery.isError` → ErrorBanner above archive
- `archiveQuery.data.length === 0` → EmptyState "No reports archived yet"

### U12 — Global disabled-on-loading audit

Walk every `<Button>` / `<PillButton>` that triggers a mutation. If the
adjacent query/mutation is pending, the button must visually disable AND
prevent double-fire.

Spec: a button is "loading-disabled" when ANY of:
- The mutation it fires is `isPending`
- The data it edits is being refetched (`isFetching` after invalidate)
- A parent prop `disabled` is true

Add `disabled` + `aria-busy="true"` attrs accordingly. The `<Button>`
component already accepts `loading` prop — propagate through.

Look at filter chip controls, "↻ FORCE REFRESH" universe button, "Run"
backtest button, favorite toggle, "Download" buttons, "+ ADD STRATEGY"
button placeholder.

## Components to use (already in `apps/web/src/components/ui/`)

- `<Skeleton>` (Skeleton.tsx) — variants: line | card | text
- `<EmptyState>` (EmptyState.tsx) — props: icon, title, description, action
- `<ErrorBanner>` (ErrorBanner.tsx) — props: title, message, onRetry
- `<Pager>` (Pager.tsx) — already used in RunHistoryTab; verify pagination
  controls disable during isLoading

Read each component first to see its exact prop signature before using it.

## Tests

Use Vitest + Testing Library. For each updated tab, add tests in the
existing `*.test.tsx`:

1. **U4 ResearchConsolePage** —
   - mock `getOverview` to return a never-resolving Promise → assert page
     shows a loader element (e.g., `data-testid="page-skeleton"`)
   - mock `getOverview` to reject → assert ErrorBanner visible

2. **U5 BacktestStudioTab** —
   - mock detail query pending → assert form area shows skeleton
   - mock detail query error → assert ErrorBanner with retry button
   - click retry → expect refetch to be called

3. **U7 RunHistoryTab** —
   - mock listRuns return `{items: [], total: 0}` with no filters → assert
     EmptyState "No backtests yet"
   - same with q="zzz" → assert "No runs match these filters" + clear button
   - click clear-filters → expect filter chips reset (use existing state
     mechanism)
   - mock isLoading=true → assert skeleton rows count = 5

4. **U9 ReportsExportsTab** —
   - mock featured query error → ErrorBanner inside card, download button disabled
   - mock archive empty → EmptyState

5. **U12 cross-tab** —
   - Universe: while refreshUniverse.isPending → assert "↻ FORCE REFRESH"
     has `disabled` and `aria-busy="true"`
   - History: while toggle favorite mutation pending → assert star button
     disabled
   - Builder: while register mutation pending → "Run" button disabled

Aim for +6 to +10 new test cases total. Existing tests must still pass.

## Frontend test setup

Tests use `@testing-library/react` + `vitest`. Use `QueryClientProvider`
wrapper helper if it already exists in `test-utils`; otherwise inline a
fresh `QueryClient` per test with `defaultOptions.queries.retry = false`.

For mocking, use `vi.mock("../../lib/api")` and replace specific exports.

## Out of scope

- No new endpoints
- No mock_data changes
- No `+ ADD STRATEGY` modal real implementation (that's Batch 10 U10)
- No `+ NEW REPORT` modal (Batch 10 U11)
- No a11y deep audit (Batch 14 A2-A4)

## Acceptance

- `cd apps/web && npm run test -- --run` all green
- `cd apps/web && npm run typecheck` clean
- `cd apps/web && npm run lint` clean
- `python -m pytest tests/ -q` still 113 passed (no backend regression)
- Manual smoke (developer must do once): launch frontend, kill the backend
  mid-session, verify each tab shows ErrorBanner not a blank panel

## Files expected to change

- `apps/web/src/pages/ResearchConsolePage.tsx` + `.test.tsx`
- `apps/web/src/features/backtest/BacktestStudioTab.tsx` + `.test.tsx`
- `apps/web/src/features/history/RunHistoryTab.tsx` + `.test.tsx`
- `apps/web/src/features/reports/ReportsExportsTab.tsx` + `.test.tsx`
- Potentially `apps/web/src/components/ui/Button.tsx` — only if `loading`
  prop needs adjustment for aria-busy
- ~250-400 LOC total

## Determinism

No new timers, no new useEffects with deps, no global state. State purely
from TanStack Query.
