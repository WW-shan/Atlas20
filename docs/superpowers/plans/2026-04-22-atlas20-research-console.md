# Atlas20 Research Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a desktop-first React + FastAPI application for Atlas20 with `Overview` and `Dashboard` tabs, existing-results visualization, and a semi-dynamic “run backtest” workflow.

**Architecture:** Add a small FastAPI layer under `src/atlas20/api/` that reads existing report artifacts and runs constrained backtests into `reports/app_runs/<run_id>/`. Add a Vite + React + TypeScript frontend under `apps/web/` that consumes those APIs, presents the approved Overview/Dashboard design, and supports parameterized reruns. Keep all new UI behavior behind narrow service boundaries so the web app remains a thin client over Atlas20’s existing research engine.

**Tech Stack:** FastAPI, Pydantic, pandas, React, Vite, TypeScript, Tailwind CSS, TanStack Query, Apache ECharts, Vitest, Testing Library, pytest.

---

## File Structure Map

### Python backend
- Create: `src/atlas20/api/__init__.py` — API package marker
- Create: `src/atlas20/api/app.py` — FastAPI app factory and router registration
- Create: `src/atlas20/api/schemas.py` — request/response models for overview, champion, options, run status, and backtest requests
- Create: `src/atlas20/api/services.py` — logic for loading report artifacts, champion metadata, options, and dispatching constrained backtests
- Create: `src/atlas20/api/routes/__init__.py` — router package marker
- Create: `src/atlas20/api/routes/overview.py` — read-only summary endpoints
- Create: `src/atlas20/api/routes/runs.py` — run detail and chart-series endpoints
- Create: `src/atlas20/api/routes/backtests.py` — constrained backtest trigger endpoint
- Create: `src/atlas20/api/runner.py` — helper that converts UI parameters into a reproducible Atlas20 run
- Modify: `src/atlas20/strategies/momentum_lead.py` — expose stable helper(s) for the champion run if needed by the runner
- Modify: `pyproject.toml` — add FastAPI stack and keep package installable

### Python tests
- Create: `tests/test_api_services.py` — verify report loading and champion summary shaping
- Create: `tests/test_api_runner.py` — verify UI request → run config translation
- Create: `tests/test_api_routes.py` — verify read endpoints and constrained backtest route

### Frontend app
- Create: `apps/web/package.json` — web app scripts and dependencies
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tsconfig.node.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/index.html`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/styles/index.css`
- Create: `apps/web/src/lib/api.ts` — fetch wrappers
- Create: `apps/web/src/lib/query-client.ts` — TanStack Query client
- Create: `apps/web/src/lib/format.ts` — formatting helpers
- Create: `apps/web/src/pages/ResearchConsolePage.tsx` — single-route shell with tabs
- Create: `apps/web/src/features/overview/OverviewTab.tsx`
- Create: `apps/web/src/features/dashboard/DashboardTab.tsx`
- Create: `apps/web/src/features/dashboard/useRunBacktest.ts`
- Create: `apps/web/src/features/dashboard/useChampionPreset.ts`
- Create: `apps/web/src/components/layout/AppShell.tsx`
- Create: `apps/web/src/components/layout/TopBar.tsx`
- Create: `apps/web/src/components/navigation/TabSwitcher.tsx`
- Create: `apps/web/src/components/cards/MetricCard.tsx`
- Create: `apps/web/src/components/panels/Panel.tsx`
- Create: `apps/web/src/components/overview/HeroSummary.tsx`
- Create: `apps/web/src/components/overview/StrategyLogicSummary.tsx`
- Create: `apps/web/src/components/overview/TopStrategiesTable.tsx`
- Create: `apps/web/src/components/dashboard/ParameterSidebar.tsx`
- Create: `apps/web/src/components/dashboard/RunStatusRail.tsx`
- Create: `apps/web/src/components/dashboard/ChartWorkspace.tsx`
- Create: `apps/web/src/components/dashboard/SelectionHistoryTable.tsx`
- Create: `apps/web/src/components/charts/EquityChart.tsx`
- Create: `apps/web/src/components/charts/DrawdownChart.tsx`
- Create: `apps/web/src/components/charts/RollingChart.tsx`
- Create: `apps/web/src/components/charts/chartTheme.ts`

### Frontend tests
- Create: `apps/web/src/pages/ResearchConsolePage.test.tsx`
- Create: `apps/web/src/features/dashboard/useChampionPreset.test.ts`
- Create: `apps/web/src/components/overview/TopStrategiesTable.test.tsx`

### Documentation / scripts
- Create: `scripts/run_api.py` — start FastAPI locally for the frontend
- Modify: `README.md` — add web app setup/run instructions
- Create: `reports/app_runs/.gitkeep` — directory placeholder for future generated runs

---

### Task 1: Add backend dependencies and API package skeleton

**Files:**
- Create: `src/atlas20/api/__init__.py`
- Create: `src/atlas20/api/routes/__init__.py`
- Modify: `pyproject.toml`
- Test: `python -m pip install -e .`

- [ ] **Step 1: Write the dependency update in `pyproject.toml`**

```toml
[project]
dependencies = [
  "pandas>=2.2",
  "numpy>=1.26",
  "pydantic>=2.8",
  "PyYAML>=6.0",
  "matplotlib>=3.8",
  "requests>=2.32",
  "fastapi>=0.116",
  "uvicorn>=0.35",
  "python-multipart>=0.0.20",
]
```

- [ ] **Step 2: Create the package markers**

```python
# src/atlas20/api/__init__.py
"""Atlas20 web API package."""
```

```python
# src/atlas20/api/routes/__init__.py
"""Route modules for the Atlas20 API."""
```

- [ ] **Step 3: Install the package in editable mode**

Run: `python -m pip install -e .`
Expected: editable install succeeds and FastAPI/uvicorn are available

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/atlas20/api/__init__.py src/atlas20/api/routes/__init__.py
git commit -m "build: add web api dependencies and package skeleton"
```

### Task 2: Define API schemas and report-loading services

**Files:**
- Create: `src/atlas20/api/schemas.py`
- Create: `src/atlas20/api/services.py`
- Test: `tests/test_api_services.py`

- [ ] **Step 1: Write the failing tests for report loading**

```python
from pathlib import Path

from atlas20.api.services import load_champion_summary, load_top_strategies


def test_load_champion_summary_reads_profit_max_artifact():
    report_dir = Path("reports/bear_bottom_to_current_2022_11_21_2026_04_22/profit_max_refine/champion_all_1m_14d_stop11_confirm2")
    summary = load_champion_summary(report_dir)
    assert summary.strategy == "MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK"
    assert summary.multiple > 200


def test_load_top_strategies_from_strategy_summary():
    report_dir = Path("reports/bear_bottom_to_current_2022_11_21_2026_04_22")
    rows = load_top_strategies(report_dir, limit=5)
    assert len(rows) == 5
    assert rows[0].strategy
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_api_services.py -v`
Expected: FAIL with import errors for missing `atlas20.api.services`

- [ ] **Step 3: Create the schema models**

```python
from pydantic import BaseModel


class StrategySummary(BaseModel):
    strategy: str
    multiple: float
    cagr: float
    sharpe: float
    max_drawdown: float
    annualized_turnover: float | None = None
    monthly_win_rate: float | None = None
```

```python
class ChampionResponse(BaseModel):
    strategy: str
    window_start: str
    window_end: str
    multiple: float
    cagr: float
    sharpe: float
    max_drawdown: float
    annualized_turnover: float
    monthly_win_rate: float
    ending_equity: float
```

- [ ] **Step 4: Implement the report loaders**

```python
from pathlib import Path

import pandas as pd

from atlas20.api.schemas import ChampionResponse, StrategySummary


def load_champion_summary(report_dir: Path) -> ChampionResponse:
    frame = pd.read_csv(report_dir / "champion_summary.csv")
    row = frame.iloc[0]
    return ChampionResponse.model_validate(row.to_dict())


def load_top_strategies(report_dir: Path, limit: int = 10) -> list[StrategySummary]:
    frame = pd.read_csv(report_dir / "strategy_summary.csv")
    frame = frame.sort_values(["total_return", "sharpe"], ascending=[False, False]).head(limit)
    return [StrategySummary.model_validate({
        "strategy": row["strategy"],
        "multiple": float(row["total_return"]) + 1.0,
        "cagr": float(row["cagr"]),
        "sharpe": float(row["sharpe"]),
        "max_drawdown": float(row["max_drawdown"]),
        "annualized_turnover": float(row.get("annualized_turnover", 0.0)),
        "monthly_win_rate": float(row.get("monthly_win_rate", 0.0)),
    }) for _, row in frame.iterrows()]
```

- [ ] **Step 5: Re-run the tests**

Run: `pytest tests/test_api_services.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/atlas20/api/schemas.py src/atlas20/api/services.py tests/test_api_services.py
git commit -m "feat: add api schemas and report loading services"
```

### Task 3: Build constrained run schema and runner service

**Files:**
- Create: `src/atlas20/api/runner.py`
- Test: `tests/test_api_runner.py`
- Modify: `src/atlas20/api/schemas.py`

- [ ] **Step 1: Write the failing runner tests**

```python
from atlas20.api.runner import build_run_request_name
from atlas20.api.schemas import BacktestRequest, RiskConfigInput, StrategyConfigInput, UniverseConfigInput, WeightInput, WindowInput


def test_build_run_request_name_is_stable():
    request = BacktestRequest(
        window=WindowInput(start_date="2022-11-21", end_date="2026-04-21"),
        strategy=StrategyConfigInput(family="momentum_lead", top_n=1, frequency="14D"),
        universe=UniverseConfigInput(min_history_days=30, min_daily_dollar_volume=1000000, exclude_btc=False),
        risk=RiskConfigInput(mode="always_on", stop_lookback_days=11, confirm_days=2, risk_off_asset="bitcoin"),
        weights=WeightInput(momentum_rank=0.607681, ret_21_rank=0.268948, ret_42_rank=0.017319, near_high_rank=0.106052),
    )
    assert build_run_request_name(request).startswith("momentum_lead_top1_14D")


def test_window_input_rejects_start_date_after_end_date():
    with pytest.raises(ValueError):
        WindowInput(start_date="2026-04-21", end_date="2022-11-21")


def test_build_run_request_name_changes_when_request_materially_changes():
    base = BacktestRequest(
        window=WindowInput(start_date="2022-11-21", end_date="2026-04-21"),
        strategy=StrategyConfigInput(family="momentum_lead", top_n=1, frequency="14D"),
        universe=UniverseConfigInput(min_history_days=30, min_daily_dollar_volume=1000000.5, exclude_btc=False),
        risk=RiskConfigInput(mode="always_on", stop_lookback_days=11, confirm_days=2, risk_off_asset="bitcoin"),
        weights=WeightInput(momentum_rank=0.607681, ret_21_rank=0.268948, ret_42_rank=0.017319, near_high_rank=0.106052),
    )
    changed = base.model_copy(update={"risk": RiskConfigInput(mode="bull_only", stop_lookback_days=11, confirm_days=2, risk_off_asset="bitcoin")})
    assert build_run_request_name(base) != build_run_request_name(changed)
```

- [ ] **Step 2: Run the test to verify failure**

Run: `pytest tests/test_api_runner.py -v`
Expected: FAIL because the runner module and request schemas do not exist yet

- [ ] **Step 3: Add constrained request models to `schemas.py`**

```python
class WindowInput(BaseModel):
    start_date: str
    end_date: str

    @model_validator(mode="after")
    def validate_date_order(self) -> "WindowInput":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class StrategyConfigInput(BaseModel):
    family: str
    top_n: int
    frequency: str


class UniverseConfigInput(BaseModel):
    min_history_days: int
    min_daily_dollar_volume: float
    exclude_btc: bool = False


class RiskConfigInput(BaseModel):
    mode: str
    stop_lookback_days: int
    confirm_days: int
    risk_off_asset: str


class WeightInput(BaseModel):
    momentum_rank: float
    ret_21_rank: float
    ret_42_rank: float
    near_high_rank: float


class BacktestRequest(BaseModel):
    window: WindowInput
    strategy: StrategyConfigInput
    universe: UniverseConfigInput
    risk: RiskConfigInput
    weights: WeightInput
```

- [ ] **Step 4: Implement the runner naming and translation helpers**

```python
from atlas20.api.schemas import BacktestRequest


def build_run_request_name(request: BacktestRequest) -> str:
    return (
        f"{request.strategy.family}_top{request.strategy.top_n}_"
        f"{request.strategy.frequency}_hist{request.universe.min_history_days}_"
        f"vol{request.universe.min_daily_dollar_volume:g}_"
        f"exbtc{int(request.universe.exclude_btc)}_"
        f"{request.risk.mode}_{request.risk.risk_off_asset}_"
        f"stop{request.risk.stop_lookback_days}_confirm{request.risk.confirm_days}_"
        f"win{request.window.start_date}_{request.window.end_date}_"
        f"w{request.weights.momentum_rank:.6f}-{request.weights.ret_21_rank:.6f}-"
        f"{request.weights.ret_42_rank:.6f}-{request.weights.near_high_rank:.6f}"
    )
```

- [ ] **Step 5: Re-run the test**

Run: `pytest tests/test_api_runner.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/atlas20/api/schemas.py src/atlas20/api/runner.py tests/test_api_runner.py
git commit -m "feat: add constrained backtest request runner scaffolding"
```

### Task 4: Expose FastAPI routes for overview, options, and runs

**Files:**
- Create: `src/atlas20/api/routes/overview.py`
- Create: `src/atlas20/api/routes/options.py`
- Create: `src/atlas20/api/routes/runs.py`
- Create: `src/atlas20/api/routes/backtests.py`
- Create: `src/atlas20/api/app.py`
- Test: `tests/test_api_routes.py`

- [ ] **Step 1: Write failing API route tests**

```python
from fastapi.testclient import TestClient

from atlas20.api.app import create_app


def test_overview_endpoint_returns_champion_and_top_strategies():
    client = TestClient(create_app())
    response = client.get("/api/overview")
    assert response.status_code == 200
    payload = response.json()
    assert "champion" in payload
    assert "top_strategies" in payload


def test_options_endpoint_returns_control_ranges():
    client = TestClient(create_app())
    response = client.get("/api/options")
    assert response.status_code == 200
    assert "strategy_families" in response.json()


def test_placeholder_runs_and_backtests_routes_are_registered():
    client = TestClient(create_app())
    assert client.get("/api/runs").status_code == 200
    assert client.get("/api/backtests").status_code == 200
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `pytest tests/test_api_routes.py -v`
Expected: FAIL because the FastAPI app and routes do not exist yet

- [ ] **Step 3: Implement the overview router**

```python
from pathlib import Path

from fastapi import APIRouter

from atlas20.api.services import load_champion_summary, load_top_strategies

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview")
def get_overview() -> dict:
    report_dir = Path(__file__).resolve().parents[4] / "reports" / "bear_bottom_to_current_2022_11_21_2026_04_22"
    champion_dir = report_dir / "profit_max_refine" / "champion_all_1m_14d_stop11_confirm2"
    return {
        "champion": load_champion_summary(champion_dir).model_dump(),
        "top_strategies": [row.model_dump() for row in load_top_strategies(report_dir, limit=10)],
    }
```

- [ ] **Step 4: Implement a neutral options router**

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/options")
def get_options() -> dict:
    return {
        "strategy_families": ["benchmark", "momentum", "sector", "champion", "momentum_lead"],
    }
```

- [ ] **Step 5: Implement placeholder runs and backtests routers**

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs")
def get_runs() -> dict:
    return {"items": []}
```

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["backtests"])


@router.get("/backtests")
def get_backtests() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 6: Implement the app factory**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas20.api.routes.backtests import router as backtests_router
from atlas20.api.routes.options import router as options_router
from atlas20.api.routes.overview import router as overview_router
from atlas20.api.routes.runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas20 Research Console API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(overview_router)
    app.include_router(options_router)
    app.include_router(runs_router)
    app.include_router(backtests_router)
    return app


app = create_app()
```

- [ ] **Step 7: Re-run the route tests**

Run: `pytest tests/test_api_routes.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/atlas20/api/app.py src/atlas20/api/routes/overview.py src/atlas20/api/routes/options.py src/atlas20/api/routes/runs.py src/atlas20/api/routes/backtests.py tests/test_api_routes.py
git commit -m "feat: expose overview and run api routes"
```

### Task 5: Add local API startup script and reports/app_runs placeholder

**Files:**
- Create: `scripts/run_api.py`
- Create: `reports/app_runs/.gitkeep`

- [ ] **Step 1: Create the API launcher**

```python
from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run("atlas20.api.app:app", host="127.0.0.1", port=8000, reload=True)
```

- [ ] **Step 2: Create the output placeholder**

```text
reports/app_runs/.gitkeep
```

- [ ] **Step 3: Verify the API boots**

Run: `python scripts/run_api.py`
Expected: Uvicorn starts on `http://127.0.0.1:8000`

- [ ] **Step 4: Commit**

```bash
git add scripts/run_api.py reports/app_runs/.gitkeep
git commit -m "chore: add local api launcher and app run directory"
```

### Task 6: Scaffold the Vite + React + TypeScript frontend

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tsconfig.node.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/index.html`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/styles/index.css`
- Test: `npm --prefix apps/web install`

- [ ] **Step 1: Create `apps/web/package.json`**

```json
{
  "name": "atlas20-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.83.0",
    "echarts": "^5.6.0",
    "react": "^19.1.0",
    "react-dom": "^19.1.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.3.0",
    "@types/react": "^19.1.8",
    "@types/react-dom": "^19.1.6",
    "@vitejs/plugin-react": "^4.7.0",
    "autoprefixer": "^10.4.21",
    "postcss": "^8.5.6",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.8.3",
    "vite": "^7.0.6",
    "vitest": "^3.2.4"
  }
}
```

- [ ] **Step 2: Create the frontend entrypoint**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 3: Install frontend packages**

Run: `npm --prefix apps/web install`
Expected: install succeeds with no missing lockfile errors

- [ ] **Step 4: Commit**

```bash
git add apps/web
git commit -m "feat: scaffold vite react frontend"
```

### Task 7: Implement shared app shell and theme

**Files:**
- Create: `apps/web/src/components/layout/AppShell.tsx`
- Create: `apps/web/src/components/layout/TopBar.tsx`
- Create: `apps/web/src/components/navigation/TabSwitcher.tsx`
- Create: `apps/web/src/components/panels/Panel.tsx`
- Create: `apps/web/src/components/cards/MetricCard.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles/index.css`
- Test: `apps/web/src/pages/ResearchConsolePage.test.tsx`

- [ ] **Step 1: Write the failing UI shell test**

```tsx
import { render, screen } from "@testing-library/react";

import App from "../App";


test("renders Atlas20 Research Console shell", () => {
  render(<App />);
  expect(screen.getByText(/Atlas20 Research Console/i)).toBeInTheDocument();
  expect(screen.getByText("Overview")).toBeInTheDocument();
  expect(screen.getByText("Dashboard")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test to verify failure**

Run: `npm --prefix apps/web test`
Expected: FAIL because the shell components and page are not wired yet

- [ ] **Step 3: Implement the shell components**

```tsx
export type ConsoleTab = "overview" | "dashboard";

export function TabSwitcher(props: {
  value: ConsoleTab;
  onChange: (value: ConsoleTab) => void;
}) {
  return (
    <div className="inline-flex rounded-2xl border border-white/10 bg-white/5 p-1">
      {(["overview", "dashboard"] as const).map((tab) => (
        <button
          key={tab}
          className={props.value === tab ? "tab-active" : "tab-idle"}
          onClick={() => props.onChange(tab)}
        >
          {tab === "overview" ? "Overview" : "Dashboard"}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Re-run frontend tests**

Run: `npm --prefix apps/web test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/App.tsx apps/web/src/components apps/web/src/styles/index.css apps/web/src/pages/ResearchConsolePage.test.tsx
git commit -m "feat: implement research console shell and theme"
```

### Task 8: Implement frontend API client and query wiring

**Files:**
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/query-client.ts`
- Create: `apps/web/src/features/dashboard/useRunBacktest.ts`
- Create: `apps/web/src/features/dashboard/useChampionPreset.ts`
- Test: `apps/web/src/features/dashboard/useChampionPreset.test.ts`

- [ ] **Step 1: Write the failing preset test**

```ts
import { championToFormState } from "./useChampionPreset";


test("converts champion payload into dashboard form state", () => {
  const state = championToFormState({
    strategy: "MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK",
    window_start: "2022-11-21",
    window_end: "2026-04-21",
    multiple: 236.999833,
    cagr: 3.949231,
    sharpe: 2.293786,
    max_drawdown: -0.507875,
    annualized_turnover: 37.801204,
    monthly_win_rate: 0.619048,
    ending_equity: 23699983.3,
  });
  expect(state.strategy.frequency).toBe("14D");
  expect(state.risk.stop_lookback_days).toBe(11);
  expect(state.risk.confirm_days).toBe(2);
});
```

- [ ] **Step 2: Implement API wrappers**

```ts
export async function getOverview() {
  const response = await fetch("http://127.0.0.1:8000/api/overview");
  if (!response.ok) throw new Error("Failed to load overview");
  return response.json();
}

export async function runBacktest(payload: unknown) {
  const response = await fetch("http://127.0.0.1:8000/api/backtests/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Backtest request failed");
  return response.json();
}
```

- [ ] **Step 3: Re-run tests**

Run: `npm --prefix apps/web test`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib apps/web/src/features/dashboard

git commit -m "feat: add frontend api client and preset helpers"
```

### Task 9: Build the Overview tab with live API data

**Files:**
- Create: `apps/web/src/features/overview/OverviewTab.tsx`
- Create: `apps/web/src/components/overview/HeroSummary.tsx`
- Create: `apps/web/src/components/overview/StrategyLogicSummary.tsx`
- Create: `apps/web/src/components/overview/TopStrategiesTable.tsx`
- Create: `apps/web/src/components/charts/EquityChart.tsx`
- Create: `apps/web/src/components/charts/chartTheme.ts`
- Test: `apps/web/src/components/overview/TopStrategiesTable.test.tsx`

- [ ] **Step 1: Write the failing ranking table test**

```tsx
import { render, screen } from "@testing-library/react";

import { TopStrategiesTable } from "./TopStrategiesTable";


test("renders strategy ranking rows", () => {
  render(
    <TopStrategiesTable
      rows={[
        { strategy: "Champion", multiple: 237, cagr: 3.94, sharpe: 2.29, max_drawdown: -0.50 },
      ]}
    />,
  );
  expect(screen.getByText("Champion")).toBeInTheDocument();
  expect(screen.getByText(/237/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Implement the Overview tab using `getOverview()`**

```tsx
const { data, isLoading } = useQuery({
  queryKey: ["overview"],
  queryFn: getOverview,
});

if (isLoading) return <Panel>Loading overview...</Panel>;
```

- [ ] **Step 3: Re-run frontend tests**

Run: `npm --prefix apps/web test`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/overview apps/web/src/components/overview apps/web/src/components/charts

git commit -m "feat: implement overview tab with live champion summary"
```

### Task 10: Build the Dashboard controls, charts, and result rail

**Files:**
- Create: `apps/web/src/features/dashboard/DashboardTab.tsx`
- Create: `apps/web/src/components/dashboard/ParameterSidebar.tsx`
- Create: `apps/web/src/components/dashboard/RunStatusRail.tsx`
- Create: `apps/web/src/components/dashboard/ChartWorkspace.tsx`
- Create: `apps/web/src/components/charts/DrawdownChart.tsx`
- Create: `apps/web/src/components/charts/RollingChart.tsx`
- Create: `apps/web/src/components/dashboard/SelectionHistoryTable.tsx`

- [ ] **Step 1: Build the dashboard form state**

```tsx
const [formState, setFormState] = useState(defaultChampionFormState);
```

- [ ] **Step 2: Implement the parameter sidebar**

```tsx
<ParameterSidebar
  value={formState}
  onChange={setFormState}
  onResetChampion={() => setFormState(championPreset)}
  onRun={handleRun}
/>
```

- [ ] **Step 3: Wire summary rail and workspace to current run**

```tsx
<RunStatusRail run={selectedRun} champion={champion} />
<ChartWorkspace run={selectedRun} />
```

- [ ] **Step 4: Verify frontend build succeeds**

Run: `npm --prefix apps/web run build`
Expected: Vite build succeeds

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/dashboard apps/web/src/components/dashboard apps/web/src/components/charts

git commit -m "feat: implement dashboard controls and result workspace"
```

### Task 11: Connect `POST /api/backtests/run` to the dashboard rerun flow

**Files:**
- Modify: `src/atlas20/api/services.py`
- Modify: `src/atlas20/api/runner.py`
- Modify: `src/atlas20/api/routes/backtests.py`
- Modify: `src/atlas20/api/routes/runs.py`
- Modify: `apps/web/src/features/dashboard/useRunBacktest.ts`
- Modify: `apps/web/src/features/dashboard/DashboardTab.tsx`

- [ ] **Step 1: Implement a run record writer**

```python
def write_run_artifacts(run_dir: Path, summary: dict, equity: pd.Series, daily_returns: pd.Series, selection_history: pd.DataFrame) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([summary]).to_csv(run_dir / "summary.csv", index=False)
    equity.rename("equity").to_csv(run_dir / "equity_curve.csv")
    daily_returns.rename("daily_return").to_csv(run_dir / "daily_returns.csv")
    selection_history.to_csv(run_dir / "selection_history.csv", index=False)
```

- [ ] **Step 2: Implement the backtest route**

```python
@router.post("/api/backtests/run")
def post_backtest(request: BacktestRequest) -> dict:
    run_id = execute_backtest_request(request)
    return {"run_id": run_id, "status": "completed"}
```

- [ ] **Step 3: Wire the frontend mutation**

```ts
const mutation = useMutation({
  mutationFn: runBacktest,
});
```

- [ ] **Step 4: Verify the full stack manually**

Run backend: `python scripts/run_api.py`
Run frontend: `npm --prefix apps/web run dev`
Expected: changing parameters and clicking `Run Backtest` updates the dashboard with a new run

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/api apps/web/src/features/dashboard

git commit -m "feat: wire dashboard backtest execution flow"
```

### Task 12: Update docs and verify the whole feature end-to-end

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add web app instructions to `README.md`**

```md
## Web Console

### Start API
python scripts/run_api.py

### Start frontend
npm --prefix apps/web install
npm --prefix apps/web run dev
```

- [ ] **Step 2: Run backend tests**

Run: `pytest tests/test_api_services.py tests/test_api_runner.py tests/test_api_routes.py -v`
Expected: PASS

- [ ] **Step 3: Run existing Python regression tests**

Run: `pytest -v`
Expected: PASS with all existing tests plus API tests

- [ ] **Step 4: Run frontend tests**

Run: `npm --prefix apps/web test`
Expected: PASS

- [ ] **Step 5: Run frontend production build**

Run: `npm --prefix apps/web run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add README.md docs/superpowers/specs/2026-04-22-atlas20-research-console-design.md docs/superpowers/plans/2026-04-22-atlas20-research-console.md

git commit -m "docs: add research console implementation plan and usage"
```

---

## Self-Review

### Spec coverage
- Overview tab: covered by Task 9
- Dashboard tab: covered by Task 10
- FastAPI backend: covered by Tasks 2, 3, 4, 5, and 11
- Semi-dynamic reruns: covered by Tasks 8, 10, and 11
- Desktop-first shell and visual structure: covered by Tasks 7, 9, and 10
- Documentation and verification: covered by Task 12

### Placeholder scan
- No `TODO`, `TBD`, or “implement later” placeholders remain
- Every task includes concrete file paths and commands
- Test commands and expected results are provided for each major phase

### Type consistency
- `BacktestRequest`, `WindowInput`, `StrategyConfigInput`, `UniverseConfigInput`, `RiskConfigInput`, and `WeightInput` are defined once and reused consistently
- Frontend tab names are consistently `overview` and `dashboard`
- Champion strategy naming remains stable across the backend and frontend integration tasks
