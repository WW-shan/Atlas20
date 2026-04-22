# Atlas20 Research Console Design Spec

**Date:** 2026-04-22  
**Project:** Atlas20 Rotation  
**Product Name:** Atlas20 Research Console

---

## 1. Goal

Build a desktop-first frontend experience for Atlas20 that combines:

1. an **investor-facing strategy presentation layer**, and  
2. a **semi-dynamic research dashboard** that can modify parameters and trigger new backtests.

The product should present the current champion strategy clearly, compare it against BTC and other benchmarks, and let the user explore or rerun research without dropping into the terminal.

---

## 2. Primary Audience

### Primary users
- the strategy author / quant researcher
- technically sophisticated crypto investors
- collaborators reviewing strategy logic and output

### Secondary users
- portfolio or research stakeholders who need a clean summary view
- external viewers evaluating whether the framework is serious, reproducible, and credible

---

## 3. Product Positioning

This should **not** feel like:
- a generic admin dashboard
- a toy crypto landing page
- a pure internal engineering panel

It should feel like:
- a **research-grade investor console**
- a **credible quant product surface**
- a **desktop-first analysis tool** with premium polish

Working positioning:

> Atlas20 Research Console = investor overview + semi-dynamic strategy dashboard

---

## 4. Experience Principles

1. **Data first**  
   Data, metrics, and comparative interpretation should dominate the experience.

2. **Professional before flashy**  
   Premium polish is desirable, but the interface must remain trustworthy and restrained.

3. **Investor overview first, research depth second**  
   Users should understand the winning strategy quickly, then drill into configuration and comparison.

4. **Desktop-first efficiency**  
   Layout, information density, and charting should be optimized for large screens.

5. **Semi-dynamic, not uncontrolled**  
   Users can change supported parameters and trigger new runs, but cannot arbitrarily execute code.

---

## 5. Information Architecture

The app uses a **single top-level route** with **two tabs**.

### Route
- `/`

### Tabs
1. `Overview`
2. `Dashboard`

This avoids unnecessary navigation complexity while preserving a clear distinction between:
- presentation / storytelling
- exploration / parameterized reruns

---

## 6. Tab Definitions

### 6.1 Overview Tab

Purpose: communicate the strategy story quickly and credibly.

#### Required sections
1. **Hero summary**
   - product name
   - short subtitle
   - current champion strategy badge

2. **Champion KPI cards**
   - final multiple
   - CAGR
   - Sharpe
   - max drawdown
   - turnover (optional in first row or second row)

3. **Primary comparison chart**
   - champion strategy vs BTC vs selected baseline(s)
   - equity curve is the default chart

4. **Strategy logic summary**
   - top-20 universe rule
   - leader selection rule
   - risk-off / BTC parking rule
   - rebalance cadence

5. **Top strategy ranking table**
   - top runs or top strategies by chosen ranking metric
   - should support at least champion + major comparators

6. **Primary CTA**
   - `Open Dashboard`

#### UX tone
- more spacious than Dashboard
- more narrative
- fewer controls
- optimized for presentation and trust

---

### 6.2 Dashboard Tab

Purpose: enable semi-dynamic research iteration inside the app.

#### Layout
Three-column desktop layout:

1. **Left rail: parameter controls**
2. **Center: charts and analytical views**
3. **Right rail: run summary and status**

#### Left rail groups
- Window
- Strategy
- Universe
- Risk Overlay
- Scoring Weights
- Actions

#### Center workspace tabs
- Equity
- Drawdown
- Rolling
- Selection History

#### Right rail content
- current run status
- selected strategy summary
- champion comparison summary
- export/download actions

#### UX tone
- denser than Overview
- optimized for manipulation and evaluation
- must still feel polished, not like a raw developer tool

---

## 7. Visual Design Direction

Final selected visual direction:

> **A + C hybrid**  
> Institutional Research Dark + subtle Premium Glass polish

### 7.1 Visual keywords
- institutional
- research-grade
- premium dark
- data-first
- subtle glass
- desktop quant console

### 7.2 Explicitly avoid
- loud cyberpunk aesthetics
- neon-heavy crypto clichés
- overly decorative glassmorphism
- shallow SaaS marketing visuals that reduce trust

---

## 8. Color System

### Base palette
- deep background navy / blue-black
- dark layered panels
- muted blue-grey borders

### Accent palette
- primary accent: blue
- secondary accent: violet / purple
- positive values: green
- risk / drawdown: red
- rare prestige highlight: amber / gold

### Color rules
- 80% dark neutral structure
- 15% blue / violet interaction emphasis
- 5% amber / special-state emphasis

This keeps the app premium and modern without overwhelming the quantitative content.

---

## 9. Typography

### Primary UI font
- **IBM Plex Sans**

Reason:
- communicates professionalism and financial trust
- reads well in dense dashboards
- feels serious enough for investor-facing presentation

### Secondary / utility font
- **Fira Code**

Use only for:
- strategy IDs
- parameter summaries
- run IDs
- some numeric displays where a technical feel is beneficial

Do **not** use monospace as the main UI font.

---

## 10. Core Components

### 10.1 Overview components
- `HeroSummary`
- `ChampionMetricCards`
- `BenchmarkEquityChart`
- `StrategyLogicSummary`
- `TopStrategiesTable`
- `OpenDashboardCTA`

### 10.2 Dashboard components
- `ParameterSidebar`
- `WindowControls`
- `StrategyControls`
- `UniverseControls`
- `RiskControls`
- `WeightSliders`
- `RunBacktestButton`
- `ResultSummaryRail`
- `RunStatusCard`
- `ChartWorkspace`
- `SelectionHistoryTable`

### 10.3 Shared components
- `TabSwitcher`
- `MetricCard`
- `Badge`
- `DataTable`
- `Panel`
- `EmptyState`
- `LoadingState`

---

## 11. Dashboard Interaction Model

### Parameter groups

#### Window
- start date
- end date
- optional preset ranges

#### Strategy
- strategy family
- top_n / top_k
- rebalance frequency

#### Universe
- min history days
- min daily dollar volume
- include/exclude BTC (supported variants only)

#### Risk Overlay
- risk mode
- stop lookback days
- confirm days
- risk-off asset

#### Scoring
- momentum-related weights
- weight sliders constrained to supported schema

### Primary actions
- `Run Backtest`
- `Reset to Champion`
- `Compare with Baseline`

### Expected user flow
1. open dashboard
2. inspect champion defaults
3. adjust parameters
4. run a new backtest
5. review updated metrics and charts
6. compare against champion and BTC
7. export or save outputs

---

## 12. Data Flow and Runtime Model

### Read paths
The frontend should read:
- existing report outputs from `reports/...`
- processed data-derived summaries exposed by the backend
- champion metadata and recent runs

### Write / run paths
When the user triggers a new backtest:
1. frontend submits a constrained parameter object
2. backend validates request
3. backend creates a `run_id`
4. backend invokes existing Atlas20 Python logic
5. backend writes outputs to `reports/app_runs/<run_id>/`
6. frontend polls or requests run status until complete
7. frontend renders updated result views

---

## 13. Backend API Design

### Read APIs
- `GET /api/overview`
- `GET /api/options`
- `GET /api/champion`
- `GET /api/runs/latest`

### Backtest APIs
- `POST /api/backtests/run`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/equity`
- `GET /api/runs/{run_id}/drawdown`
- `GET /api/runs/{run_id}/selection-history`

### Request design principle
The frontend should send a **controlled parameter object**, not an arbitrary config file and not arbitrary code.

---

## 14. Frontend Tech Stack

Recommended stack:
- **React**
- **Vite**
- **TypeScript**
- **Tailwind CSS**
- **ECharts**
- **TanStack Query**

### Why
- strong desktop application ergonomics
- fast chart rendering
- clean component architecture
- suitable for both polished presentation and analytical tooling

---

## 15. Backend Tech Stack

Recommended stack:
- **FastAPI**
- reuse of existing `src/atlas20` logic

### Why
- fits the current Python codebase
- lightweight API surface
- easy integration with current backtesting and report generation modules

---

## 16. Proposed File Structure

```text
apps/
  web/
    src/
      pages/
      components/
      features/
      lib/
      styles/
    index.html
    package.json
    vite.config.ts

src/atlas20/
  api/
    app.py
    schemas.py
    services.py
    routes/

reports/
  app_runs/
```

---

## 17. MVP Definition

The first release must include:

1. `Overview` tab
2. `Dashboard` tab
3. champion strategy loading
4. benchmark comparison display
5. parameter editing UI
6. backtest trigger from UI
7. refreshed KPI + charts after run completion

If those are delivered, the product is already meaningful.

---

## 18. Out of Scope for MVP

Do not include in first version:
- arbitrary shell execution
- free-form code editing from UI
- full job orchestration platform
- multi-user auth system
- mobile-first optimization
- advanced collaboration features

---

## 19. Implementation Priorities

### Phase 1
- frontend shell
- Overview tab
- Dashboard layout
- read existing CSV/JSON-backed results

### Phase 2
- FastAPI integration
- trigger new run from UI
- run status and result refresh

### Phase 3
- comparison tools
- saved runs
- export improvements
- champion restore / presets

---

## 20. Acceptance Criteria

The design is successful if:

1. an investor can understand the champion strategy and key outperformance quickly
2. a researcher can modify parameters and rerun analysis without leaving the page
3. the product feels credible, premium, and data-centric
4. the interface works best on desktop and does not collapse into a generic admin dashboard
5. the UI supports ongoing research rather than just static storytelling

---

## 21. Final Direction Summary

The final approved design direction is:

- **structure:** Overview + Dashboard dual-tab model
- **visual style:** Institutional Research Dark with subtle Premium Glass polish
- **UX mode:** desktop-first semi-dynamic research console
- **technology:** React/Vite frontend + FastAPI backend + existing Atlas20 backtest engine

This is the design baseline for implementation.
