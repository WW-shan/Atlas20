# Review: P7 Strategy Compare + P8 Run History

## Tooling

- Gemini reviewer pass could not run: `gemini command not found in PATH`.
- Claude reviewer wrapper exceeded the first timeout and was stopped.
- Local checks:
  - `npm test -- --run src/features/compare/StrategyCompareTab.test.tsx src/features/history/RunHistoryTab.test.tsx` passed.
  - `npm run build` failed outside scope at `src/features/universe/UniverseHealthTab.tsx(98,41)`.

## Findings

### Critical

- `apps/web/src/features/history/RunHistoryTab.tsx:76` / `apps/web/src/features/history/RunHistoryTab.tsx:83`: server-mode data is treated as already filtered but then paginated again with `items.slice(start, start + pageSize)`. Since `listRuns(filter)` returns paged `{ items, total, page, pageSize }`, page 2+ from the API will typically render empty.
- `apps/web/src/components/history/Toolbar.tsx:73`: the active date-range tab uses `var(--gold)` as a filled segmented control. The gold whitelist only permits top-nav active underline/text, primary CTA, one chart line, best-cell tint, and Jaccard diagonal in this reviewed scope.
- `apps/web/src/components/compare/StrategyChip.tsx:9`: the `gold` strategy chip paints chip text, border, dot, and background gold. Strategy chips are not on the gold whitelist.
- `apps/web/src/features/compare/StrategyCompareTab.tsx:76`: the local range tabs use gold active text and `apps/web/src/features/compare/StrategyCompareTab.tsx:77` uses a gold underline. The allowed tab gold treatment is for the active top nav tab, not nested range controls.
- `apps/web/src/features/history/RunHistoryTab.tsx:86` / `apps/web/src/components/history/RunTable.tsx:92`: page4 spec calls for row selection plus `RE-RUN SELECTED -> navigate("backtest", prefillRunId)` and selected-row a11y, but the implementation directly opens a row on click with no selected state or `aria-selected`.

### Warning

- `apps/web/src/components/history/RunTable.tsx:39`: `COLS` defines 11 columns, while the P4 test/spec minimum requires 13 columns.
- `apps/web/src/features/compare/StrategyCompareTab.test.tsx:73`: the range-switching test only checks `aria-selected`; it does not verify that the TanStack query key changes through `qk.compare(ids, range)` as required by the P3 checklist.
- `apps/web/src/features/history/RunHistoryTab.test.tsx:18`: the date-range coverage only checks the default `30d` active tab; it does not click date ranges or verify the query + chips + date range stack.
- `apps/web/src/features/history/RunHistoryTab.test.tsx:31`: the table coverage accepts `>=10` rows and does not assert the required 14 fallback rows, 13 columns, pagination behavior, or `RE-RUN SELECTED` navigation.

### Info

- `apps/web/src/features/compare/StrategyCompareTab.tsx:131`: the `BEST` legend uses `tone="gold-outline"`. If the gold whitelist is interpreted strictly as only the best data-cell tint, this legend is another stray gold use.
