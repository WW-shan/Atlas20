# Review: bc69153 Phase 9 Universe and P7/P8 fixes

## Critical

- `apps/web/src/components/compare/StrategyChip.tsx:9` / `apps/web/src/components/compare/StrategyChip.tsx:46` — Strategy chips still render a gold dot for the ATLAS item, outside the supplied gold whitelist and contrary to the gold-restraint fix scope.
- `apps/web/src/components/universe/UniverseTimeline.tsx:69` / `apps/web/src/features/universe/UniverseHealthTab.tsx:81` — Universe active segments and legend still use `var(--gold)`, but the requested whitelist does not include Universe timeline gold.

## Warning

- `apps/web/src/features/compare/StrategyCompareTab.tsx:136` / `apps/web/src/features/compare/StrategyCompareTab.tsx:137` / `apps/web/src/features/compare/StrategyCompareTab.tsx:138` — The BEST legend uses gold styling even though only the best cells themselves are whitelisted.
- `apps/web/src/features/universe/UniverseHealthTab.tsx:29` / `apps/web/src/features/universe/UniverseHealthTab.tsx:36` / `apps/web/src/features/universe/UniverseHealthTab.tsx:43` — Universe queries use `initialData` and the component has no loading/error/empty rendering, so the SPEC query-state baseline is not actually exercised.
- `apps/web/src/components/universe/DataAlertRow.tsx:66` / `apps/web/src/components/universe/DataAlertRow.tsx:68` / `apps/web/src/components/universe/DataAlertRow.tsx:69` — `border` is applied after `borderLeft`, so the intended 3px severity bar is reset to a 1px border with only the color restored.

## Info

- `apps/web/src/components/universe/UniverseTimeline.tsx:107` / `apps/web/src/components/universe/UniverseTimeline.tsx:117` — SVG date labels use the mono font but not the `.mono` class or `font-variant-numeric: tabular-nums`; add explicit tabular numeric styling for strict rule #8 compliance.
- Targeted tests passed: `npm test -- UniverseHealthTab RunHistoryTab`.
