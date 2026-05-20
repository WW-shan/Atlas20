You are the codex FIXER for Batch 6 remaining Info findings.

Per the new protocol (`.ccg/process/batch-execution-protocol.md` rev `48afe0e`),
all findings — including Info — get fixed. Claude has decided the exact UX
direction for each; you implement.

## Info #1 — ResearchConsolePage ErrorBanner + cached data overlap

**File:** `apps/web/src/pages/ResearchConsolePage.tsx:65-76`

**Current:** when `overviewQuery.isError && overviewQuery.data !== undefined`,
both `<ErrorBanner>` (full width) AND `<OverviewTab data={...} />` render.

**Claude's decision:** Stale data is more useful than a blank error screen.
Hide the full ErrorBanner when cached data exists; show a small inline
`<Pill tone="rose" size="xs">stale — refresh failed</Pill>` at the top-right
of the page header (sibling of the existing tab nav). Add `aria-live="polite"`
so screen readers announce the stale state without grabbing focus.

**Implementation:**
- Render full-page `<ErrorBanner ... onRetry={...} />` ONLY when
  `overviewQuery.isError && !overviewQuery.data`.
- When `isError && data` → render `<OverviewTab data={data} />` plus a small
  `<Pill tone="rose" size="xs" aria-live="polite">stale — refresh failed</Pill>`
  near the page header. Clicking the pill calls `overviewQuery.refetch()`.
  Make the pill a button (`<button>` wrapping `<Pill>`).
- Add `data-testid="overview-stale-indicator"` for testability.

**Test:** add one Vitest case in `ResearchConsolePage.test.tsx`:
- Mock first query success then second refetch error.
- Assert OverviewTab still renders with cached data AND the stale pill is
  visible (no full ErrorBanner).

## Info #2 — BacktestStudio skeleton + sidebar overlap

**File:** `apps/web/src/features/backtest/BacktestStudioTab.tsx:87-94`

**Current:** `<DetailPrefillSkeleton>` AND `<ParameterSidebar>` both render
when `detailQuery.isLoading`. Two cards stack on top of each other.

**Claude's decision:** Skeleton REPLACES the sidebar only on initial load
(no cached data yet). On refetch (cached data present + isFetching), keep
sidebar and show a subtle inline `<Spinner size="xs">` in the sidebar header.

**Implementation:**
- Condition: `detailQuery.isLoading && !detailQuery.data` → render
  `<DetailPrefillSkeleton>` and DO NOT render `<ParameterSidebar>`.
- Else render `<ParameterSidebar>` as today.
- For refetch state (`detailQuery.isFetching && detailQuery.data`),
  pass `refreshing` prop to `ParameterSidebar` so it shows a small inline
  spinner badge near its title. If `ParameterSidebar` doesn't accept that
  prop yet, add it.

**Test:** update existing test to confirm skeleton does NOT coexist with
sidebar; add a new test for the refetch case showing both sidebar AND
spinner badge.

## Info #3 — useRunQueue.ts

**Claude's decision:** KEEP. It's symmetric with `useRunBacktest.ts` and
12 lines is fine. No code changes — only ADD a one-line comment at the top:

```ts
// Paired with useRunBacktest — both manipulate the same queue cache.
```

No tests needed.

## Info #4 — `lint` script aliases tsc

**File:** `apps/web/package.json`

**Current:** `"lint": "tsc -b --pretty false"` — same as typecheck.

**Claude's decision:** Wire up real ESLint with TypeScript + React Hooks
plugins. Minimal config, react-query plugin not required.

**Implementation:**
1. Add devDeps:
   - `eslint` (^9.x)
   - `@typescript-eslint/parser`
   - `@typescript-eslint/eslint-plugin`
   - `eslint-plugin-react`
   - `eslint-plugin-react-hooks`
   - `eslint-plugin-jsx-a11y`

2. Add `apps/web/eslint.config.js` (flat config) with:
   - parser: `@typescript-eslint/parser`
   - parserOptions: project ./tsconfig.json
   - plugins: react, react-hooks, jsx-a11y, @typescript-eslint
   - rules: `react-hooks/rules-of-hooks: error`,
     `react-hooks/exhaustive-deps: warn`, `jsx-a11y/aria-busy: error`,
     `@typescript-eslint/no-unused-vars: error`,
     `@typescript-eslint/no-explicit-any: warn`,
     `react/jsx-key: error`.
   - extends recommended sets where possible (flat-config style).
   - ignore: `dist/`, `node_modules/`, `*.test.tsx` for some rules.

3. Update `package.json`:
   - `"lint": "eslint src --max-warnings=0"`
   - keep `"typecheck": "tsc -b"`

4. Fix any actual lint violations surfaced — should be few since codex
   already wrote clean code. If too many, raise `--max-warnings` and
   leave a TODO.

**Test:** none (build-time tool).

## Procedure

Each fix = SEPARATE commit:

1. `fix(ui): batch 6 reviewer pass — stale-data pill instead of full ErrorBanner on overview refetch`
2. `fix(ui): batch 6 reviewer pass — skeleton replaces sidebar only on initial load`
3. `docs(ui): batch 6 reviewer pass — document useRunQueue pairing`
4. `chore(ui): batch 6 reviewer pass — wire real ESLint with TS/React/a11y plugins`

After each commit:
- `cd apps/web && npm run test -- --run` green
- `cd apps/web && npm run typecheck` green
- After commit #4: `cd apps/web && npm run lint` green (or `--max-warnings`
  bumped with TODO comment)
- `python -m pytest tests/ -q` still 113

## Report

- Four commit hashes
- Final frontend test count
- npm lint output summary (rule violations count)
- Any deviations
