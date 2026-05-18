# Review: c67225a Phase 7 StrategyCompareTab

## Verification

- `npm test -- StrategyCompareTab.test.tsx` in `apps/web`: passed, 10 tests.
- `npm run build` in `apps/web`: failed in existing out-of-scope history code:
  - `src/components/history/RunTable.tsx(1,23)` missing `RunStatusEnum` export.
  - `src/components/history/RunTable.tsx(11,45)` missing return path.
- `git diff --check c67225a^ c67225a -- <scoped paths>`: passed.
- Claude reviewer pass completed.
- Gemini reviewer pass failed because `gemini` is not available on PATH.

## Findings

### Critical

- `apps/web/src/components/compare/StrategyChip.tsx:9` and `apps/web/src/features/compare/StrategyCompareTab.tsx:19`: ATLAS is assigned `tone: "gold"` and `StrategyChip` renders that as gold border, text, background tint, and dot. SPEC section 1.1 allows page3 gold for the ATLAS equity line, best-cell tint, and Jaccard diagonal; the chip itself is not on the gold whitelist.

### Warning

- `apps/web/src/features/compare/StrategyCompareTab.tsx:47`: the `role="list"` for "Selected strategies" contains the three strategy listitems, but also contains the add button at line 51 and count text at line 52. Those are not selected-strategy `listitem`s, so the accessible list has mixed children under a selected-strategies label.
- `apps/web/src/components/compare/JaccardHeatmap.tsx:34` and `apps/web/src/components/compare/JaccardHeatmap.tsx:86`: the heatmap parent is exposed as a single `role="img"`, while each cell is a generic, non-focusable `div` with `aria-label`. Screen readers can expose only the parent image label and ignore the per-cell labels, so the SPEC requirement for individual heatmap cell labels is not reliably met.
- `apps/web/src/features/compare/StrategyCompareTab.tsx:62`: the range control declares `role="tablist"`/`role="tab"` and `aria-selected`, but it does not implement tab keyboard behavior such as arrow-key navigation or roving focus. Native button activation works, but the ARIA tab pattern is incomplete.

### Info

- `apps/web/src/features/compare/StrategyCompareTab.test.tsx:73`: the range-switch test only asserts `aria-selected`; it does not verify the SPEC minimum that switching range updates the compare query key.
