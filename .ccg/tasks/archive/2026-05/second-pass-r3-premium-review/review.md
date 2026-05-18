## Critical

- Reports download handlers discard the `{ url }` returned by `downloadDigest` / `downloadReport`, so the buttons make a JSON request but never start a browser download. `ReportsExportsTab.tsx:61`, `ReportsExportsTab.tsx:66`, `api.ts:603`, `api.ts:607`.
- Backtest prefill can show/cache the wrong run detail: every selected `prefillRunId` uses `fallbackRunDetail` for `btk_0142` as `initialData`, so navigating from history to another run initially renders the wrong run and can keep it if the request fails. `BacktestStudioTab.tsx:40`, `BacktestStudioTab.tsx:44`, `api.ts:405`.

## Warning

- Data queries use `initialData` fallback and render `data ?? fallback` without loading/error/empty branches, which suppresses the SPEC-required query states and seeds fallback into cache. Representative sites: `ResearchConsolePage.tsx:41`, `StrategyCompareTab.tsx:33`, `UniverseHealthTab.tsx:26`, `ReportsExportsTab.tsx:34`.
- `FeaturedDigest.defaultFormat` is ignored; the UI always initializes `format` to `"markdown"`, so an API digest with a different default renders the wrong active format. `ReportsExportsTab.tsx:31`, `api.ts:263`.
- Universe alert count treats resolved/emerald alerts as open. The badge displays all alerts as `OPEN` even though fallback includes a resolved emerald alert. `UniverseHealthTab.tsx:58`, `UniverseHealthTab.tsx:115`, `api.ts:485`.
- Universe refresh invalidates `["universe"]` directly instead of using the qk registry, violating SPEC query-key centralization. `UniverseHealthTab.tsx:49`, `qk.ts:28`.
- Gold restraint/CTA mismatches remain: non-whitelisted gold is used for hero/status labels and report archive highlight, while whitelisted primary CTAs `+ NEW REPORT` and `FORCE REFRESH` are violet outlines. `OverviewTab.tsx:74`, `OverviewTab.tsx:84`, `FeaturedDigestHero.tsx:18`, `ReportCard.tsx:35`, `ReportCard.tsx:44`, `ReportsExportsTab.tsx:119`, `UniverseHealthTab.tsx:66`.
- History row selection is mouse-only: clickable `<tr>` elements are not focusable and have no keyboard handler, so keyboard users cannot select a row before `RE-RUN SELECTED`. `RunTable.tsx:97`, `RunTable.tsx:104`.
- Overview equity range uses `span role="tab"` for non-focusable, non-interactive items. Either remove tab semantics or implement real keyboard/focus behavior. `OverviewTab.tsx:133`, `OverviewTab.tsx:135`.
- Parameter number inputs do not enforce their own bounds in state; clearing/typing can send `0` or out-of-range values despite `min`/`max`, and the local `clamp` helper is unused. `ParameterSidebar.tsx:12`, `ParameterSidebar.tsx:142`, `ParameterSidebar.tsx:147`, `ParameterSidebar.tsx:158`, `ParameterSidebar.tsx:161`.

## Info

- `+ ADD STRATEGY` is a visible no-op: `StrategyCompareTab` keeps selections without a setter and renders `AddStrategyChip` without `onClick`. `StrategyCompareTab.tsx:28`, `StrategyCompareTab.tsx:50`, `StrategyChip.tsx:74`.
- Dev-only console output remains on the `+ NEW REPORT` stub. `ReportsExportsTab.tsx:70`.
- `Pager` renders one button per page; large totals create unbounded DOM work. `Pager.tsx:9`, `Pager.tsx:25`.
- `OverlayLineChart` emits duplicate `key="xl-0"` x-axis labels for one-point series. `OverlayLineChart.tsx:143`, `OverlayLineChart.tsx:145`.
- Verification: `npm --prefix apps/web test -- --run` passed 10 files / 106 tests. `npm --prefix apps/web run build` completed `tsc -b && vite build` successfully.
