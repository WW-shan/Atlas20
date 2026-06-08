# Strategy Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Strategy Lab console tab that queues a small parameter matrix and ranks completed batch results.

**Architecture:** The backend adds a narrow Strategy Lab API that expands a matrix into ordinary `BacktestConfig` runs, storing the batch id on the `runs` table. The frontend adds a new console tab with matrix controls, polling batch status, and a ranked results table while reusing the existing Backtest/History/worker flow.

**Tech Stack:** FastAPI, SQLModel, Alembic, Pydantic v2, React 19, TanStack Query, Vitest, Playwright.

---

## File Structure

- Modify `src/atlas20/api/db/models.py`: add nullable `Run.strategy_lab_batch_id`.
- Create `src/atlas20/api/db/migrations/versions/20260608_0001_strategy_lab_batch_id.py`: add/drop the nullable column and index.
- Modify `src/atlas20/api/schemas.py`: add Strategy Lab request/response/result schemas.
- Modify `src/atlas20/api/repositories/runs_repo.py`: add `list_by_strategy_lab_batch`.
- Modify `src/atlas20/api/services/__init__.py`: add matrix expansion, batch submission, and batch payload functions.
- Create `src/atlas20/api/routes/strategy_lab.py`: expose Strategy Lab routes.
- Modify `src/atlas20/api/app.py`: include the new router.
- Modify `apps/web/src/lib/api.ts`: add Strategy Lab types and API helpers.
- Modify `apps/web/src/lib/qk.ts`: add Strategy Lab query keys.
- Create `apps/web/src/features/strategy-lab/StrategyLabTab.tsx`: tab orchestration and polling.
- Create `apps/web/src/features/strategy-lab/StrategyLabControls.tsx`: matrix controls.
- Create `apps/web/src/features/strategy-lab/StrategyLabResultsTable.tsx`: ranked results.
- Modify `apps/web/src/components/navigation/TabSwitcher.tsx`: add tab key and label.
- Modify `apps/web/src/pages/ResearchConsolePage.tsx`: mount the new tab.
- Add tests in `tests/test_strategy_lab.py`, `apps/web/src/features/strategy-lab/StrategyLabTab.test.tsx`, and `apps/web/e2e/console.smoke.spec.ts`.

---

### Task 1: Backend Data Model And Schemas

**Files:**
- Modify: `src/atlas20/api/db/models.py`
- Create: `src/atlas20/api/db/migrations/versions/20260608_0001_strategy_lab_batch_id.py`
- Modify: `src/atlas20/api/schemas.py`
- Modify: `src/atlas20/api/repositories/runs_repo.py`
- Test: `tests/test_strategy_lab.py`

- [ ] **Step 1: Write failing repository/schema tests**

Add `tests/test_strategy_lab.py`:

```python
from datetime import date, datetime, timezone

import pytest
from sqlmodel import Session

from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.schemas import BacktestConfig, StrategyLabMatrixRequest


def valid_config() -> dict:
    return {
        "preset": "base",
        "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
        "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Monthly"},
        "allocation": {"positionPct": 10, "slots": 10},
        "costs": {"feeBps": 10, "slippageBps": 5},
    }


def test_strategy_lab_matrix_request_validates_payload() -> None:
    request = StrategyLabMatrixRequest.model_validate(
        {
            "presets": ["base"],
            "topNs": [10, 20],
            "rebalances": ["Weekly", "Monthly"],
            "baseConfig": valid_config(),
        }
    )

    assert request.presets == ["base"]
    assert request.top_ns == [10, 20]
    assert request.base_config == BacktestConfig.model_validate(valid_config())


def test_runs_repo_lists_runs_by_strategy_lab_batch(db_session: Session) -> None:
    db_session.add(
        Run(
            run_id="btk_9991",
            strategy="base",
            strategy_family="Other",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="completed",
            return_pct=0.2,
            sharpe=1.4,
            max_dd=-0.15,
            strategy_lab_batch_id="lab_test",
            created_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    rows = RunsRepo(db_session).list_by_strategy_lab_batch("lab_test")

    assert [row.run_id for row in rows] == ["btk_9991"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src /tmp/atlas20-venv/bin/python -m pytest tests/test_strategy_lab.py -q
```

Expected: failures because `StrategyLabMatrixRequest`, `top_ns`, `strategy_lab_batch_id`, and `list_by_strategy_lab_batch` do not exist.

- [ ] **Step 3: Add model, migration, schemas, and repository method**

Implementation details:

```python
# src/atlas20/api/db/models.py inside Run
strategy_lab_batch_id: str | None = Field(default=None, index=True)
```

```python
# src/atlas20/api/repositories/runs_repo.py inside RunsRepo
def list_by_strategy_lab_batch(self, batch_id: str) -> builtins.list[Run]:
    stmt = (
        select(Run)
        .where(Run.strategy_lab_batch_id == batch_id)
        .order_by(col(Run.created_at).desc(), col(Run.run_id).desc())
    )
    return builtins.list(self._s.exec(stmt).all())
```

```python
# src/atlas20/api/schemas.py
class StrategyLabMatrixRequest(StrictApiModel):
    presets: list[str] = Field(min_length=1)
    top_ns: list[int] = Field(alias="topNs", min_length=1)
    rebalances: list[Literal["Weekly", "Biweekly", "Monthly"]] = Field(min_length=1)
    base_config: BacktestConfig = Field(alias="baseConfig")


class StrategyLabResult(ApiModel):
    run_id: str
    preset: str
    topN: int
    rebalance: Literal["Weekly", "Biweekly", "Monthly"]
    status: RunStatusEnum
    return_pct: float | None = None
    sharpe: float | None = None
    max_dd: float | None = None
    calmar: float | None = None


class StrategyLabBatchResponse(ApiModel):
    batch_id: str
    runs: list[RunRowSummary]
    total: int


class StrategyLabBatchPayload(ApiModel):
    batch_id: str
    status_counts: dict[str, int]
    runs: list[RunRow]
    results: list[StrategyLabResult]
```

Migration:

```python
"""add strategy lab batch id

Revision ID: 20260608_0001
Revises: 20260521_0001
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260608_0001"
down_revision: Union[str, Sequence[str], None] = "20260521_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("strategy_lab_batch_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_runs_strategy_lab_batch_id"), "runs", ["strategy_lab_batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_runs_strategy_lab_batch_id"), table_name="runs")
    op.drop_column("runs", "strategy_lab_batch_id")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONPATH=src /tmp/atlas20-venv/bin/python -m pytest tests/test_strategy_lab.py -q
```

Expected: the new tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/api/db/models.py src/atlas20/api/db/migrations/versions/20260608_0001_strategy_lab_batch_id.py src/atlas20/api/schemas.py src/atlas20/api/repositories/runs_repo.py tests/test_strategy_lab.py
git commit -m "feat: add strategy lab batch model"
```

---

### Task 2: Backend Strategy Lab API

**Files:**
- Modify: `src/atlas20/api/services/__init__.py`
- Create: `src/atlas20/api/routes/strategy_lab.py`
- Modify: `src/atlas20/api/app.py`
- Test: `tests/test_strategy_lab.py`, `tests/test_api_routes.py`

- [ ] **Step 1: Write failing service and route tests**

Append to `tests/test_strategy_lab.py`:

```python
from atlas20.api import services


def test_submit_strategy_lab_batch_queues_matrix(db_session: Session) -> None:
    request = StrategyLabMatrixRequest.model_validate(
        {
            "presets": ["base"],
            "topNs": [10, 20],
            "rebalances": ["Weekly", "Monthly"],
            "baseConfig": valid_config(),
        }
    )

    response = services.submit_strategy_lab_batch(db_session, request)

    assert response.total == 4
    assert response.batch_id.startswith("lab_")
    assert {run.strategy for run in response.runs} == {"base"}
    rows = RunsRepo(db_session).list_by_strategy_lab_batch(response.batch_id)
    assert len(rows) == 4
    assert {row.universe for row in rows} == {"Top-10", "Top-20"}


def test_submit_strategy_lab_batch_rejects_oversized_matrix(db_session: Session) -> None:
    request = StrategyLabMatrixRequest.model_validate(
        {
            "presets": ["base"] * 5,
            "topNs": [5, 10, 15],
            "rebalances": ["Weekly", "Biweekly"],
            "baseConfig": valid_config(),
        }
    )

    with pytest.raises(ValueError, match="at most 24"):
        services.submit_strategy_lab_batch(db_session, request)


def test_get_strategy_lab_batch_returns_counts_and_results(db_session: Session) -> None:
    request = StrategyLabMatrixRequest.model_validate(
        {
            "presets": ["base"],
            "topNs": [20],
            "rebalances": ["Monthly"],
            "baseConfig": valid_config(),
        }
    )
    response = services.submit_strategy_lab_batch(db_session, request)
    run_id = response.runs[0].run_id
    RunsRepo(db_session).update(
        run_id,
        status="completed",
        return_pct=0.24,
        sharpe=1.9,
        max_dd=-0.12,
        duration_s=42,
    )

    payload = services.get_strategy_lab_batch(db_session, response.batch_id)

    assert payload.batch_id == response.batch_id
    assert payload.status_counts["completed"] == 1
    assert payload.results[0].run_id == run_id
    assert payload.results[0].topN == 20
```

Add a route test to `tests/test_api_routes.py`:

```python
def test_strategy_lab_batch_route_queues_runs(client: TestClient):
    response = client.post(
        "/api/strategy-lab/batches",
        json={
            "presets": ["base"],
            "topNs": [20],
            "rebalances": ["Monthly"],
            "baseConfig": REPORT_REQUEST,
        },
        headers={"X-API-Key": "valid-key"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["total"] == 1
    assert payload["batch_id"].startswith("lab_")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src /tmp/atlas20-venv/bin/python -m pytest tests/test_strategy_lab.py tests/test_api_routes.py::test_strategy_lab_batch_route_queues_runs -q
```

Expected: failures because service functions and route do not exist.

- [ ] **Step 3: Implement services and route**

Service implementation outline:

```python
STRATEGY_LAB_MAX_RUNS = 24
TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


def _strategy_lab_batch_id(request: StrategyLabMatrixRequest) -> str:
    digest = hashlib.sha1(request.model_dump_json(by_alias=True).encode("utf-8")).hexdigest()[:8]
    return f"lab_{utc_now().strftime('%Y%m%d%H%M%S')}_{digest}"


def _strategy_lab_configs(request: StrategyLabMatrixRequest) -> list[BacktestConfig]:
    configs = []
    for preset in request.presets:
        for top_n in request.top_ns:
            for rebalance in request.rebalances:
                data = request.base_config.model_dump(mode="json")
                data["preset"] = preset
                data["universe"]["topN"] = top_n
                data["window"]["rebalance"] = rebalance
                configs.append(BacktestConfig.model_validate(data))
    if not configs:
        raise ValueError("strategy lab matrix must include at least one run")
    if len(configs) > STRATEGY_LAB_MAX_RUNS:
        raise ValueError("strategy lab matrix can queue at most 24 runs")
    return configs


def submit_strategy_lab_batch(session: Session, request: StrategyLabMatrixRequest) -> StrategyLabBatchResponse:
    batch_id = _strategy_lab_batch_id(request)
    summaries = []
    for config in _strategy_lab_configs(request):
        summary = register_new_backtest(session, config, strategy_lab_batch_id=batch_id)
        summaries.append(summary)
    return StrategyLabBatchResponse(batch_id=batch_id, runs=summaries, total=len(summaries))
```

Route implementation:

```python
router = APIRouter(prefix="/api", tags=["strategy-lab"])


@router.post("/strategy-lab/batches", response_model=StrategyLabBatchResponse, status_code=202, dependencies=[Depends(verify_api_key)])
def post_strategy_lab_batch(request: StrategyLabMatrixRequest, session: Session = Depends(get_session)) -> StrategyLabBatchResponse:
    try:
        return services.submit_strategy_lab_batch(session, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONPATH=src /tmp/atlas20-venv/bin/python -m pytest tests/test_strategy_lab.py tests/test_api_routes.py::test_strategy_lab_batch_route_queues_runs -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/atlas20/api/services/__init__.py src/atlas20/api/routes/strategy_lab.py src/atlas20/api/app.py tests/test_strategy_lab.py tests/test_api_routes.py
git commit -m "feat: add strategy lab api"
```

---

### Task 3: Frontend API Types And Query Keys

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/qk.ts`
- Test: `apps/web/src/lib/api.test.ts`

- [ ] **Step 1: Write failing frontend API tests**

Append to `apps/web/src/lib/api.test.ts`:

```ts
it("submitStrategyLabBatch posts the matrix payload", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    batch_id: "lab_test",
    runs: [],
    total: 0,
  }))));
  const api = await import("./api");

  await api.submitStrategyLabBatch({
    presets: ["base"],
    topNs: [20],
    rebalances: ["Monthly"],
    baseConfig: api.defaultBacktestConfig,
  });

  const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/strategy-lab/batches");
  expect(JSON.parse(String(init.body)).topNs).toEqual([20]);
});

it("getStrategyLabBatch fetches a batch by id", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    batch_id: "lab_test",
    status_counts: { queued: 1, running: 0, completed: 0, failed: 0, cancelled: 0 },
    runs: [],
    results: [],
  }))));
  const api = await import("./api");

  await api.getStrategyLabBatch("lab_test");

  expect(vi.mocked(fetch).mock.calls[0][0]).toBe("/api/strategy-lab/batches/lab_test");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
npm --prefix apps/web test -- src/lib/api.test.ts
```

Expected: failures because helpers and types do not exist.

- [ ] **Step 3: Implement API helpers and query key**

Add types and helpers in `apps/web/src/lib/api.ts`:

```ts
export type StrategyLabMatrixRequest = {
  presets: string[];
  topNs: number[];
  rebalances: BacktestConfig["window"]["rebalance"][];
  baseConfig: BacktestConfig;
};

export type StrategyLabResult = {
  run_id: string;
  preset: string;
  topN: number;
  rebalance: BacktestConfig["window"]["rebalance"];
  status: RunStatusEnum;
  return_pct?: number | null;
  sharpe?: number | null;
  max_dd?: number | null;
  calmar?: number | null;
};

export type StrategyLabBatchResponse = {
  batch_id: string;
  runs: RunRowSummary[];
  total: number;
};

export type StrategyLabBatchPayload = {
  batch_id: string;
  status_counts: Record<RunStatusEnum, number>;
  runs: RunRow[];
  results: StrategyLabResult[];
};

export function submitStrategyLabBatch(payload: StrategyLabMatrixRequest) {
  return requestJson<StrategyLabBatchResponse>("/strategy-lab/batches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getStrategyLabBatch(batchId: string) {
  return requestJson<StrategyLabBatchPayload>(`/strategy-lab/batches/${encodeURIComponent(batchId)}`);
}
```

Add query keys:

```ts
strategyLab: {
  batch: (batchId: string) => ["strategy-lab", "batch", batchId] as const,
},
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
npm --prefix apps/web test -- src/lib/api.test.ts
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/qk.ts apps/web/src/lib/api.test.ts
git commit -m "feat: add strategy lab web api"
```

---

### Task 4: Strategy Lab UI

**Files:**
- Create: `apps/web/src/features/strategy-lab/StrategyLabControls.tsx`
- Create: `apps/web/src/features/strategy-lab/StrategyLabResultsTable.tsx`
- Create: `apps/web/src/features/strategy-lab/StrategyLabTab.tsx`
- Test: `apps/web/src/features/strategy-lab/StrategyLabTab.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Create `apps/web/src/features/strategy-lab/StrategyLabTab.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StrategyLabTab } from "./StrategyLabTab";
import * as api from "../../lib/api";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../../lib/api");
  return {
    ...actual,
    getOptions: vi.fn(),
    submitStrategyLabBatch: vi.fn(),
    getStrategyLabBatch: vi.fn(),
  };
});

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("StrategyLabTab", () => {
  beforeEach(() => {
    vi.mocked(api.getOptions).mockResolvedValue(api.fallbackOptions);
    vi.mocked(api.submitStrategyLabBatch).mockResolvedValue({ batch_id: "lab_test", runs: [], total: 2 });
    vi.mocked(api.getStrategyLabBatch).mockResolvedValue({
      batch_id: "lab_test",
      status_counts: { queued: 1, running: 0, completed: 1, failed: 0, cancelled: 0 },
      runs: [],
      results: [
        { run_id: "btk_9991", preset: "base", topN: 20, rebalance: "Monthly", status: "completed", return_pct: 0.2, sharpe: 1.5, max_dd: -0.12, calmar: 1.6 },
      ],
    });
  });

  it("renders matrix controls and run count preview", async () => {
    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    expect(await screen.findByRole("heading", { name: "Experiment matrix" })).toBeInTheDocument();
    expect(screen.getByText(/runs selected/i)).toBeInTheDocument();
  });

  it("submits the selected matrix", async () => {
    const user = userEvent.setup();
    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    await user.click(await screen.findByRole("button", { name: /Queue experiment/i }));

    await waitFor(() => expect(api.submitStrategyLabBatch).toHaveBeenCalled());
    expect(vi.mocked(api.submitStrategyLabBatch).mock.calls[0][0].baseConfig).toEqual(api.defaultBacktestConfig);
  });

  it("renders status counts and opens a completed run", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderWithQuery(<StrategyLabTab onNavigate={onNavigate} />);

    await user.click(await screen.findByRole("button", { name: /Queue experiment/i }));
    expect(await screen.findByText("lab_test")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /Open btk_9991/i }));

    expect(onNavigate).toHaveBeenCalledWith("backtest", "btk_9991");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
npm --prefix apps/web test -- src/features/strategy-lab/StrategyLabTab.test.tsx
```

Expected: failure because components do not exist.

- [ ] **Step 3: Implement controls, tab, and results table**

Implementation requirements:

- Use `Card`, `SectionHeader`, `Button`, `Pill`, `Skeleton`, `ErrorBanner`, and `EmptyState`.
- Keep layout dense and operational.
- Use checkboxes/toggles for presets, topN, and rebalance choices.
- Compute `runCount = presets.length * topNs.length * rebalances.length`.
- Poll while any status count has queued/running.
- Sort Max DD descending because less negative is better.

Core sort helper:

```ts
function sortedResults(results: StrategyLabResult[], sort: SortMetric): StrategyLabResult[] {
  const direction = sort === "max_dd" ? 1 : -1;
  return [...results].sort((a, b) => {
    const av = a[sort] ?? Number.NEGATIVE_INFINITY;
    const bv = b[sort] ?? Number.NEGATIVE_INFINITY;
    return (av - bv) * direction;
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
npm --prefix apps/web test -- src/features/strategy-lab/StrategyLabTab.test.tsx
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/strategy-lab
git commit -m "feat: build strategy lab tab"
```

---

### Task 5: Navigation, OpenAPI, And E2E

**Files:**
- Modify: `apps/web/src/components/navigation/TabSwitcher.tsx`
- Modify: `apps/web/src/pages/ResearchConsolePage.tsx`
- Modify: `apps/web/src/pages/ResearchConsolePage.test.tsx`
- Modify: `apps/web/src/test/axe.test.tsx`
- Modify: `apps/web/e2e/console.smoke.spec.ts`
- Generated: `apps/web/src/lib/api-schema.json`, `apps/web/src/lib/api.generated.ts`

- [ ] **Step 1: Write failing navigation and e2e assertions**

Update `apps/web/src/pages/ResearchConsolePage.test.tsx` tab list:

```ts
const tabNames = ["Overview", "Backtest", "Strategy Lab", "Compare", "History", "Universe", "Reports"];
```

Add e2e smoke:

```ts
test("strategy lab queues a small experiment batch", async ({ page }) => {
  await page.goto("/");
  await openConsoleTab(page, "Strategy Lab");
  await expect(page.getByRole("heading", { name: "Strategy Lab" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Experiment matrix" })).toBeVisible();
  await page.getByRole("button", { name: /Queue experiment/i }).click();
  await expect(page.getByText(/runs queued/i)).toBeVisible();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
npm --prefix apps/web test -- src/pages/ResearchConsolePage.test.tsx src/test/axe.test.tsx
```

Expected: navigation test fails because tab is not wired.

- [ ] **Step 3: Wire navigation and regenerate OpenAPI**

Changes:

```ts
// TabSwitcher.tsx
| "strategyLab"
...
{ key: "strategyLab", label: "Strategy Lab" },
```

```tsx
// ResearchConsolePage.tsx
import { StrategyLabTab } from "../features/strategy-lab/StrategyLabTab";
...
strategyLab: "Strategy Lab",
...
{nav.tab === "strategyLab" && (
  <ErrorBoundary>
    <StrategyLabTab onNavigate={navigate} />
  </ErrorBoundary>
)}
```

Regenerate schema:

```bash
PYTHONPATH=src /tmp/atlas20-venv/bin/python -m atlas20.api.openapi
npm --prefix apps/web run openapi
```

- [ ] **Step 4: Run focused tests and e2e**

Run:

```bash
PYTHONPATH=src /tmp/atlas20-venv/bin/python -m pytest tests/test_strategy_lab.py -q
npm --prefix apps/web test -- src/features/strategy-lab/StrategyLabTab.test.tsx src/pages/ResearchConsolePage.test.tsx src/test/axe.test.tsx
PATH=/tmp/atlas20-venv/bin:$PATH npm --prefix apps/web run e2e
```

Expected: focused tests and e2e pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/navigation/TabSwitcher.tsx apps/web/src/pages/ResearchConsolePage.tsx apps/web/src/pages/ResearchConsolePage.test.tsx apps/web/src/test/axe.test.tsx apps/web/e2e/console.smoke.spec.ts apps/web/src/lib/api-schema.json apps/web/src/lib/api.generated.ts
git commit -m "feat: wire strategy lab console tab"
```

---

### Task 6: Full Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run release-level verification**

Run:

```bash
PYTHONPATH=src /tmp/atlas20-venv/bin/python scripts/verify_release.py
```

Expected: repository health, pytest, Ruff, mypy, OpenAPI check, Vitest, typecheck, build, OpenAPI generated type check, pip-audit, and npm audit pass.

- [ ] **Step 2: Inspect final status**

Run:

```bash
git status -sb
git log --oneline -6
```

Expected: clean worktree on `feature/strategy-lab` after commits.

- [ ] **Step 3: Integrate**

If verification passes:

```bash
git push origin feature/strategy-lab
```

Then decide whether to merge to `main` or open a PR based on the user's requested workflow.
