# Live Research Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Live Research API and console tab, repair the confirmed compare/backtest/report defects, and prove every console control with an end-to-end journey.

**Architecture:** A new backend data-access module normalizes checked-in research artifacts into one `GET /api/live/research` payload. The frontend adds an eighth tab, fixes chart/unit conversion, removes an ineffective control, derives the default backtest end date from verified data, and completes digest downloads. Playwright then walks the full UI and inventories/exercises all visible controls.

**Tech Stack:** FastAPI, Pydantic, pandas, React 19, TanStack Query, Vitest, Testing Library, Playwright, TypeScript, OpenAPI snapshot generation.

---

### Task 1: Live research data access

**Files:**
- Create: `src/atlas20/api/data_access/live.py`
- Test: `tests/test_live_research_data_access.py`

- [ ] **Step 1: Write failing data-access tests**

Create tests that build a temporary report root containing the four source shapes:

```python
from pathlib import Path
import json
import pandas as pd
from atlas20.api.data_access.live import load_live_research
from atlas20.api.settings import Settings


def _write_spot(root: Path) -> None:
    live = root / "phase_momentum_live"
    live.mkdir(parents=True)
    (live / "latest_signal.json").write_text(json.dumps({
        "trial_id": "PR2026-10-H5",
        "as_of": "2026-10-08",
        "panel_last_date": "2026-10-08",
        "gross_exposure": 0.6214,
        "current_gross_exposure": 0.4605,
        "current_weights": {"near": 0.4605},
        "targets": {"near": 0.6214},
        "btc_gate_open": True,
        "cost_bps": 20.0,
        "rule": "strict PIT Top20",
        "last_day_check": {"complete": True, "reasons": []},
    }), encoding="utf-8")


def test_load_live_research_reads_current_spot_and_oos(tmp_path: Path):
    _write_spot(tmp_path)
    oos = tmp_path / "phase_momentum_oos_2026"
    oos.mkdir()
    (oos / "manifest.json").write_text(json.dumps({
        "trial_id": "PR2026-10-H5",
        "oos_start": "2026-09-22",
        "oos_end": "2026-10-08",
        "oos_days": 17,
    }), encoding="utf-8")
    (oos / "oos_summary.csv").write_text(
        "fill_policy,cost_bps,start,end,days,multiple\n"
        "close,20.0,2026-09-22,2026-10-08,17,0.9677\n"
        "close,100.0,2026-09-22,2026-10-08,17,0.9624\n",
        encoding="utf-8",
    )
    (oos / "benchmark.csv").write_text(
        "fill_policy,cost_bps,start,end,days,multiple\n"
        "btc_close,0.0,2026-09-22,2026-10-08,17,0.9431\n",
        encoding="utf-8",
    )
    decision = tmp_path / "phase_momentum_candidate_eval_h5"
    decision.mkdir()
    (decision / "decision_table.csv").write_text(
        "trial_id,fill_hours,worse_policy,multiple,sharpe,max_drawdown\n"
        "PR2026-10-H5,1,h1_day_close,22.8004,1.7036,-0.3327\n",
        encoding="utf-8",
    )

    payload = load_live_research(Settings(report_root=tmp_path))

    assert payload["spot"]["trial_id"] == "PR2026-10-H5"
    assert payload["spot"]["targets"] == {"near": 0.6214}
    assert payload["oos"]["multiple"] == 0.9677
    assert payload["oos"]["benchmark_multiple"] == 0.9431
    assert payload["spot"]["frozen"]["multiple"] == 22.8004
```

Add an analogous derivatives test for `derivatives_track_execution/latest.json`, `derivatives_track_live/health.json`, `audit.json`, `signal_equivalence.json`, and `journal.csv`, and a missing-artifact test that returns availability metadata rather than fabricated data.

- [ ] **Step 2: Run test and confirm failure**

Run: `.venv/bin/python -m pytest tests/test_live_research_data_access.py -q`
Expected: FAIL because `atlas20.api.data_access.live` does not exist.

- [ ] **Step 3: Implement the data-access module**

Implement:

```python
def load_live_research(settings: Settings) -> dict[str, Any]:
    """Read current research and live-operation artifacts without mutation."""
```

Required helpers:

- `_read_json(path: Path) -> dict[str, Any] | None`
- `_read_csv(path: Path) -> pd.DataFrame`
- `_spot_payload(report_root: Path) -> dict[str, Any]`
- `_oos_payload(report_root: Path) -> dict[str, Any]`
- `_derivatives_payload(report_root: Path) -> dict[str, Any]`
- `_artifact_status(report_root: Path) -> list[dict[str, str | bool]]`

Numeric parsing must use a single `_number(value, default=None)` helper. Journal rows are capped to the latest 20. All returned strings must be trimmed and non-finite values rejected/defaulted to `None`.

- [ ] **Step 4: Run test and confirm pass**

Run: `.venv/bin/python -m pytest tests/test_live_research_data_access.py -q`
Expected: PASS.

---

### Task 2: API schema, service, route, and OpenAPI

**Files:**
- Modify: `src/atlas20/api/schemas.py`
- Create: `src/atlas20/api/routes/live.py`
- Modify: `src/atlas20/api/app.py`
- Modify: `src/atlas20/api/services/__init__.py`
- Modify: `src/atlas20/api/services/protocols.py`
- Modify: `src/atlas20/api/services/real_impl.py`
- Modify: `src/atlas20/api/services/mock_impl.py`
- Modify: `src/atlas20/api/mock_data.py`
- Test: `tests/test_api_routes.py`
- Test: `tests/test_openapi_snapshot.py`

- [ ] **Step 1: Write failing route test**

In `tests/test_api_routes.py`, add a `LiveResearchPayload` import and:

```python
def test_live_research_endpoint_returns_read_only_payload(client: TestClient):
    response = client.get("/api/live/research")

    assert response.status_code == 200
    payload = LiveResearchPayload.model_validate(response.json())
    assert payload.spot.trial_id
    assert payload.artifacts
```

Also test that the route rejects unknown query parameters:

```python
def test_live_research_endpoint_rejects_unknown_query_params(client: TestClient):
    response = client.get("/api/live/research?mutate=true")
    assert response.status_code == 422
```

- [ ] **Step 2: Run route test and confirm failure**

Run: `.venv/bin/python -m pytest tests/test_api_routes.py -k live_research -q`
Expected: FAIL with 404 or import error.

- [ ] **Step 3: Implement schema and route**

Add typed models for:

- `LiveWeight`
- `LiveDataQuality`
- `LiveFrozenMetrics`
- `LiveSpotPayload`
- `LiveOosStressRow`
- `LiveOosPayload`
- `LiveAuditCheck`
- `LiveDerivativesPayload`
- `LiveJournalRow`
- `LiveArtifactStatus`
- `LiveResearchPayload`

The route must be:

```python
@router.get("/live/research", response_model=LiveResearchPayload, response_model_exclude_none=True)
def get_live_research(service: ConsoleService = Depends(get_console_service)) -> LiveResearchPayload:
    return service.get_live_research()
```

- [ ] **Step 4: Extend service protocol, real implementation, and mock implementation**

Add `get_live_research()` to all three service layers. The real implementation validates the data-access payload. The mock implementation returns `mock_data.fallback_live_research`.

- [ ] **Step 5: Regenerate OpenAPI and generated frontend types**

Run:
```bash
.venv/bin/python -m atlas20.api.openapi
npm --prefix apps/web run openapi
```

- [ ] **Step 6: Run API and OpenAPI tests**

Run:
```bash
.venv/bin/python -m pytest tests/test_api_routes.py tests/test_live_research_data_access.py tests/test_openapi_snapshot.py -q
npm --prefix apps/web run openapi:check
```

Expected: all pass.

---

### Task 3: Frontend API and query key

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/qk.ts`
- Test: `apps/web/src/lib/api.test.ts`

- [ ] **Step 1: Write failing frontend API test**

Mock `/api/live/research` and assert `getLiveResearch()` returns the typed payload.

- [ ] **Step 2: Run test and confirm failure**

Run: `npm --prefix apps/web test -- --run api.test.ts`
Expected: FAIL because `getLiveResearch` is undefined.

- [ ] **Step 3: Implement types and request**

Add `LiveResearchPayload` types matching the generated OpenAPI models, `fallbackLiveResearch`, `getLiveResearch()`, and `qk.liveResearch()`.

- [ ] **Step 4: Run frontend API tests**

Run: `npm --prefix apps/web test -- --run api.test.ts`
Expected: PASS.

---

### Task 4: Compare percentage conversion

**Files:**
- Modify: `apps/web/src/components/charts/OverlayLineChart.tsx`
- Modify: `apps/web/src/features/compare/StrategyCompareTab.tsx`
- Test: `apps/web/src/components/charts/charts.test.tsx`
- Test: `apps/web/src/features/compare/StrategyCompareTab.test.tsx`

- [ ] **Step 1: Write failing test**

Render a multiplier series ending at `0.876` and assert the Y-axis includes `-12.4%`, not `+1.0%`.

```tsx
it("converts multiplier equity values to percentage returns", () => {
  render(
    <OverlayLineChart
      series={[{ ts: "Jan", values: { a: 1 } }, { ts: "Feb", values: { a: 0.876 } }]}
      lines={[{ id: "a", label: "A", tone: "gold" }]}
      range="YTD"
      yFormat="multiplier-percent"
    />,
  );
  expect(screen.getByText("-12.4%")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test and confirm failure**

Run: `npm --prefix apps/web test -- --run charts.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement conversion**

Extend `yFormat` with `"multiplier-percent"` and format with `(value - 1) * 100`. Use it for the Compare equity overlay only; Backtest/Overview already receive percentage points.

- [ ] **Step 4: Run compare and chart tests**

Run: `npm --prefix apps/web test -- --run charts.test.tsx StrategyCompareTab.test.tsx`
Expected: PASS.

---

### Task 5: Backtest control and default-date repair

**Files:**
- Modify: `src/atlas20/api/schemas.py`
- Modify: `src/atlas20/api/data_access/options.py`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/components/backtest/ParameterSidebar.tsx`
- Modify: `apps/web/src/features/backtest/BacktestStudioTab.tsx`
- Test: `tests/test_overview_data_access.py` or `tests/test_api_routes.py`
- Test: `apps/web/src/components/backtest/ParameterSidebar.test.tsx`
- Test: `apps/web/src/features/backtest/BacktestStudioTab.test.tsx`

- [ ] **Step 1: Write failing backend/default-date test**

Assert `/api/options` includes `latestVerifiedDate == "2026-10-08"` when the live signal exists.

- [ ] **Step 2: Write failing frontend tests**

- Assert the sidebar does not render a slots input.
- Assert it renders `Slots · strategy-defined`.
- Assert Backtest Studio hydrates `window.end` to `2026-10-08` after options load.

- [ ] **Step 3: Run tests and confirm failure**

Run:
```bash
.venv/bin/python -m pytest tests/test_api_routes.py -k options -q
npm --prefix apps/web test -- --run ParameterSidebar.test.tsx BacktestStudioTab.test.tsx
```

Expected: FAIL.

- [ ] **Step 4: Implement**

- Add optional `latestVerifiedDate` to `OptionsPayload`.
- Derive it from `phase_momentum_live/latest_signal.json`, falling back to existing report data.
- Remove the slots number input from the sidebar and show a non-editable explanation.
- When options resolve and the user has not edited the date, set the default config end to `latestVerifiedDate`.

- [ ] **Step 5: Run tests**

Run the same commands. Expected: PASS.

---

### Task 6: Featured digest downloads

**Files:**
- Modify: `apps/web/src/components/reports/FeaturedDigestHero.tsx`
- Modify: `apps/web/src/features/reports/ReportsExportsTab.tsx`
- Test: `apps/web/src/features/reports/ReportsExportsTab.test.tsx`

- [ ] **Step 1: Write failing tests**

Assert all five controls render:

- `MARKDOWN`
- `PDF`
- `PNG`
- `CSV`
- `DOWNLOAD ALL`

Click `MARKDOWN` and expect `downloadDigest("markdown")`. Click `DOWNLOAD ALL` and expect `downloadDigest("bundle")`. Assert errors are displayed and pending buttons are disabled.

- [ ] **Step 2: Run test and confirm failure**

Run: `npm --prefix apps/web test -- --run ReportsExportsTab.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

Add `onDownload(format)`, `downloadBusy`, and `downloadDisabled` props to `FeaturedDigestHero`. In `ReportsExportsTab`, manage one pending format and call `downloadDigest`.

- [ ] **Step 4: Run report tests**

Run: `npm --prefix apps/web test -- --run ReportsExportsTab.test.tsx`
Expected: PASS.

---

### Task 7: Live Research tab

**Files:**
- Create: `apps/web/src/features/live/LiveResearchTab.tsx`
- Create: `apps/web/src/features/live/LiveResearchTab.test.tsx`
- Modify: `apps/web/src/components/navigation/TabSwitcher.tsx`
- Modify: `apps/web/src/pages/ResearchConsolePage.tsx`
- Modify: `apps/web/src/pages/ResearchConsolePage.test.tsx`
- Modify: `apps/web/src/styles/index.css` if layout utility classes are needed

- [ ] **Step 1: Write failing component test**

The test mocks `getLiveResearch()` and asserts:

- Spot card shows `PR2026-10-H5`, signal date, target weight, gross exposure, and provisional status.
- OOS card shows 17 days, H5 multiple, BTC multiple, and stress rows.
- Derivatives card shows health, equity, notional, hard failures, and signal equivalence.
- Journal card shows the latest row.
- `REFRESH LIVE DATA` calls `refetch` after click.

- [ ] **Step 2: Run test and confirm failure**

Run: `npm --prefix apps/web test -- --run LiveResearchTab.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement the tab and navigation**

Add `"liveResearch"` to `ConsoleTab`, render the tab in `ResearchConsolePage`, and implement the four-card layout described in the design. Use existing `Card`, `SectionHeader`, `Pill`, `Button`, and `ErrorBanner` components.

- [ ] **Step 4: Run page/component tests**

Run:
```bash
npm --prefix apps/web test -- --run LiveResearchTab.test.tsx ResearchConsolePage.test.tsx
```
Expected: PASS.

---

### Task 8: Full-journey E2E and button inventory

**Files:**
- Create: `apps/web/e2e/console.full-journey.spec.ts`
- Modify: `apps/web/e2e/console.smoke.spec.ts` if selectors need stable test IDs

- [ ] **Step 1: Write failing E2E test**

The spec must:

1. Open all eight tabs and assert each heading.
2. Record every visible button into a `Map<string, string[]>` inventory.
3. Exercise:
   - Overview quick actions.
   - Backtest workspace tabs, regenerate-report disabled/enabled state, and new-run reset.
   - Strategy Lab queue (existing real backend flow).
   - Compare range buttons and add-strategy modal.
   - History search/filter/date/view/pagination controls and re-run.
   - Universe force refresh and status transition.
   - Reports type filters, sort buttons, featured downloads, and new-report modal.
   - Live Research refresh.
4. Assert no page errors or console errors.
5. Assert the button inventory has no unknown button labels and that every inventory button was either clicked or explicitly covered by an enabled/disabled assertion.

- [ ] **Step 2: Run E2E and confirm failure**

Run: `PATH="$PWD/.venv/bin:$PATH" npm --prefix apps/web run e2e -- console.full-journey.spec.ts`
Expected: FAIL before Live Research exists and before defects are repaired.

- [ ] **Step 3: Stabilize selectors and complete the journey**

Add stable `data-testid` or accessible labels as needed. Keep destructive trading actions read-only; no E2E test may place a derivatives order.

- [ ] **Step 4: Run E2E**

Run the same command. Expected: PASS with all visible buttons exercised or covered.

---

### Task 9: Full verification and release commit

**Files:**
- All modified files from Tasks 1-8
- Update: `RESEARCH.md` only if a research conclusion changes; this task is console adaptation, so no research conclusion should be altered.

- [ ] **Step 1: Run backend tests**

```bash
.venv/bin/python -m pytest tests/ -q
```

- [ ] **Step 2: Run frontend tests**

```bash
npm --prefix apps/web test
```

- [ ] **Step 3: Run lint and type checks**

```bash
make lint
make typecheck
```

- [ ] **Step 4: Run OpenAPI and production checks**

```bash
npm --prefix apps/web run openapi:check
npm --prefix apps/web run build
```

- [ ] **Step 5: Run full E2E**

```bash
PATH="$PWD/.venv/bin:$PATH" npm --prefix apps/web run e2e
```

- [ ] **Step 6: Verify clean status and commit/push**

```bash
git status --short
git add src tests apps/web docs
git commit -m "feat: adapt console to live research state"
git push
```

Expected: clean working tree before commit, all checks pass, and main is pushed.
