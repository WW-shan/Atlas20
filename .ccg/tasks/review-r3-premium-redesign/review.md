# Review: R3 Crypto-Native Premium redesign

## Critical

- `ResearchConsolePage.tsx` uses inline `["overview"]` instead of `qk.overview()`.
- `RunHistoryTab.tsx` has a query without `initialData: fallbackRunsList`.
- `ReportsExportsTab.tsx` labels the CTA as `DOWNLOAD ALL · BUNDLE` but calls `downloadDigest(format)`.
- Multiple non-whitelisted gold usages remain across overview, backtest queue, compare legend/chips, report-card halo, and stale CSS.

## Warning

- SVG chart/timeline text uses mono font family but no `font-variant-numeric: tabular-nums`.
- Several numeric/timestamp displays are not wrapped in `.mono`.
- Backtest workspace uses non-interactive `span role="tab"` elements.
- Backtest strategy select lacks an accessible name.
- Favorite toggle is exposed by `RunTable` but never wired from `RunHistoryTab`.
- Query keys are only partially canonicalized and universe invalidation uses an inline tuple.
- Tab feature tests do not cover loading/error/empty states; Universe and Backtest key actions are not clicked.
- Stale legacy CSS remains after P11 cleanup.
- `api.test.ts` contains an unnecessary `as unknown` cast.

## Verification

- `npm --prefix apps/web test -- --run` passed.
- `npm --prefix apps/web run build` passed.
- `git diff --check` failed on trailing blank line at EOF in `components/compare/StrategyChip.tsx`.
- Gemini external reviewer failed because `gemini` is not in PATH; Claude wrapper completed but returned no captured findings.
