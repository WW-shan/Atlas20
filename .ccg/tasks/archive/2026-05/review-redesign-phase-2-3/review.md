# Review: Atlas20 Redesign Phase 2 + Phase 3

## Findings

- Critical: `Card` declares `variant?: "default" | "hero" | "report"` but only implements the hero branch. `report` falls through to default styling and has no thumbnail slot required by SPEC §6.3.
- Critical: `KpiTileProps` declares `spark?: { points; tone }` but `KpiTile` never destructures or renders `spark`, so callers can pass a contract-supported sparkline and get no output.
- Warning: `KpiTile` inline label is `11px`, while SPEC §6.2 requires inline label `14px sans uppercase` with `16px mono` value.
- Warning: `SparklineChart` defaults `height` to `32`, while SPEC §6.5 requires default `24`.
- Warning: `SkeletonProps.variant` is optional with a default, while SPEC §4 declares the variant as required.
- Warning: `ErrorBanner` uses the text glyph `⚠` instead of the `<AlertTriangle>` icon specified by SPEC §4.
- Warning: Tests do not meet the requested role/text assertion criterion for every component: `StatusDot` and `Skeleton` are checked via container queries only.
- Info: `Pill` supports pulse animation, but the type does not restrict `pulse` to cyan usage as described by SPEC §6.1.
- Info: `Button` disables during loading but cursor/opacity only key off `disabled`, not `loading`.

## Passed Checks

- `PillTone`, `ChartRange`, `RunStatusEnum`, and `ReportSortKey` unions are present in `types.ts`.
- `PillTone` contains the 9 SPEC tones; `Pill` has `xs`/`sm`/`md` sizes and renders a pulse dot animation.
- `KpiTile` has inline and non-inline branches; non-inline label is muted uppercase 11px; values use `mono`.
- `Card` exposes the 3 variants and `hero` applies `card card--hero` with 180px min height.
- `Button` has all 6 variants, including `outline-dashed`, and disables while loading.
- `Pager` renders the showing range, page numbers, and gold active page.
- `EmptyState`, `ErrorBanner`, and `Skeleton` broadly match SPEC §4 shapes aside from the noted issues.
- `SparklineChart` implements 6 tones and accepts `number[]` or point objects.
- `OverlayLineChart` implements the typed line API, gold glow filter, annotations, and chart accessibility role.
- Targeted tests passed: `npm test -- --run src/components/ui/ui.test.tsx src/components/charts/charts.test.tsx` reported 20 passed tests.

## Verification Notes

- `npm run build` fails outside the reviewed component set in `src/features/dashboard/DashboardTab.tsx` and `src/features/dashboard/useRunBacktest.ts`.
- Gemini CCG backend was unavailable because `gemini` was not found in PATH; Claude CCG reviewer completed successfully.
