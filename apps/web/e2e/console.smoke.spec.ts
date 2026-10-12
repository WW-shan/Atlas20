import { expect, test, type Page } from "@playwright/test";

import type {
  BacktestConfig,
  DataAlert,
  DataSource,
  FeaturedDigest,
  LiveResearchPayload,
  OptionsPayload,
  OverviewPayload,
  ReportEntry,
  RunRow,
  UniverseTimelinePayload,
} from "../src/lib/api";

type RunsResponse = {
  items: RunRow[];
  total: number;
  page: number;
  pageSize: number;
};

const defaultBacktestConfig: BacktestConfig = {
  preset: "base",
  universe: { topN: 20, excludeStable: true, excludeWrapped: true },
  window: { start: "2024-01-01", end: "2026-05-18", rebalance: "Weekly" },
  allocation: { positionPct: 5.0, slots: 10 },
  costs: { feeBps: 10, slippageBps: 5 },
};

async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `${path} returned ${response.status()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

async function apiPostJson<T>(page: Page, path: string, payload: unknown): Promise<T> {
  const response = await page.request.post(path, { data: payload });
  expect(response.ok(), `${path} returned ${response.status()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

async function ensureRunRow(page: Page): Promise<RunRow> {
  const completedPath = "/api/runs?q=&chips=completed&dateRange=all&page=1&pageSize=50";
  let runs = await apiJson<RunsResponse>(page, completedPath);
  if (runs.items.length === 0) {
    await apiPostJson(page, "/api/backtests/run", defaultBacktestConfig);
    runs = await apiJson<RunsResponse>(page, completedPath);
  }
  expect(runs.items.length, "expected at least one completed run row").toBeGreaterThan(0);
  return runs.items.find((run) => run.strategy !== "universe_refresh" && run.return_pct != null) ?? runs.items[0];
}

async function openConsoleTab(page: Page, name: string): Promise<void> {
  await page.getByRole("tablist", { name: "Console views" }).getByRole("tab", { name }).click();
}

test.describe("research console smoke", () => {
  test("overview renders the live champion payload", async ({ page }) => {
    const overview = await apiJson<OverviewPayload>(page, "/api/overview");

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    await expect(
      page.getByLabel("Current champion summary").getByText(overview.champion.display_name),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /RUN NEW BACKTEST/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /COMPARE STRATEGIES/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /GENERATE REPORT/i })).toBeVisible();
  });

  test("history can re-open a real run in backtest studio", async ({ page }) => {
    const selectedRun = await ensureRunRow(page);

    await page.goto("/");
    await openConsoleTab(page, "History");
    await expect(page.getByRole("heading", { name: "Run History" })).toBeVisible();
    const rerunSearch = page.getByRole("searchbox", { name: "Search runs" });
    await rerunSearch.fill(selectedRun.run_id);
    await expect(page.locator(`[data-run-id="${selectedRun.run_id}"]`)).toBeVisible();

    await page.locator(`[data-run-id="${selectedRun.run_id}"]`).click();
    await page.getByRole("button", { name: /RE-RUN SELECTED/i }).click();

    await expect(page.getByRole("heading", { name: "Backtest Studio" })).toBeVisible();
    const regenerateReport = page.getByRole("button", { name: /Regenerate this run's report/i });
    if (selectedRun.status === "completed") {
      await expect(regenerateReport).toBeEnabled();
    } else {
      await expect(regenerateReport).toBeDisabled();
    }
    await expect(page.getByText(selectedRun.run_id).first()).toBeVisible();
  });

  test("live research renders the read-only live payload", async ({ page }) => {
    const live = await apiJson<LiveResearchPayload>(page, "/api/live/research");

    await page.goto("/");
    await openConsoleTab(page, "Live");
    await expect(page.getByRole("heading", { name: "Live Research" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Spot research" })).toBeVisible();
    await expect(page.getByRole("button", { name: /REFRESH LIVE DATA/i })).toBeVisible();
    expect(live.spot?.trial_id, "expected a current spot research trial").toBeTruthy();
    expect(live.spot?.signal_date, "expected a current signal date").toBeTruthy();
    expect(live.derivatives?.health.equity, "expected derivatives health equity").toBeTruthy();
  });

  test("compare exposes real backend strategies in the add modal", async ({ page }) => {
    const options = await apiJson<OptionsPayload>(page, "/api/options");
    expect(options.strategies.length, "expected at least one real strategy option").toBeGreaterThan(0);
    const strategyLabel = options.strategies[0].display_name;

    await page.goto("/");
    await openConsoleTab(page, "Compare");
    await expect(page.getByRole("heading", { name: "Strategy Compare" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /HOLDINGS OVERLAP/i })).toBeVisible();

    await page.getByRole("button", { name: "Add strategy" }).click();
    const dialog = page.getByRole("dialog", { name: "Add strategy" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("option", { name: strategyLabel })).toBeVisible();
  });

  test("strategy lab exposes only the point-in-time Top 20 experiment controls", async ({ page }) => {
    await page.goto("/");
    await openConsoleTab(page, "Strategy Lab");
    await expect(page.getByRole("heading", { name: "Strategy Lab" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Experiment matrix" })).toBeVisible();

    await expect(page.getByText("Top 20")).toBeVisible();
    await expect(page.getByText("Top 5")).toHaveCount(0);
    await expect(page.getByText("Top 10")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Queue experiment/i })).toBeEnabled();
  });

  test("run history shows a real run row", async ({ page }) => {
    const firstRun = await ensureRunRow(page);

    await page.goto("/");
    await openConsoleTab(page, "History");
    await expect(page.getByRole("heading", { name: "Run History" })).toBeVisible();
    const historySearch = page.getByRole("searchbox", { name: "Search runs" });
    await historySearch.fill(firstRun.run_id);
    await expect(page.locator(`[data-run-id="${firstRun.run_id}"]`)).toBeVisible();
    await expect(historySearch).toBeVisible();
  });

  test("universe renders live sources and alerts", async ({ page }) => {
    const [timeline, sources, alerts] = await Promise.all([
      apiJson<UniverseTimelinePayload>(page, "/api/universe/timeline"),
      apiJson<DataSource[]>(page, "/api/universe/sources"),
      apiJson<DataAlert[]>(page, "/api/universe/alerts"),
    ]);
    expect(timeline.tokens.length, "expected a non-empty universe timeline").toBeGreaterThan(0);
    expect(sources.length, "expected live data sources").toBeGreaterThan(0);
    expect(alerts.length, "expected live data alerts").toBeGreaterThan(0);

    await page.goto("/");
    await openConsoleTab(page, "Universe");
    await expect(page.getByRole("heading", { name: "Universe & Data Health" })).toBeVisible();
    await expect(page.getByText(sources[0].name)).toBeVisible();
    await expect(page.getByText(alerts[0].title)).toBeVisible();
    await expect(page.getByRole("button", { name: /FORCE REFRESH/i })).toBeVisible();
  });

  test("reports archive lists a real artifact and opens the report modal", async ({ page }) => {
    const [featured, reports, options] = await Promise.all([
      apiJson<FeaturedDigest>(page, "/api/reports/digest/featured"),
      apiJson<ReportEntry[]>(page, "/api/reports?sort=recent"),
      apiJson<OptionsPayload>(page, "/api/options"),
    ]);
    expect(reports.length, "expected at least one report entry").toBeGreaterThan(0);

    await page.goto("/");
    await openConsoleTab(page, "Reports");
    await expect(page.getByRole("heading", { name: "Reports & Exports" })).toBeVisible();
    await expect(page.getByRole("heading", { name: featured.title })).toBeVisible();
    await expect(page.getByRole("heading", { name: reports[0].title })).toBeVisible();

    await page.getByRole("button", { name: "+ NEW REPORT" }).click();
    const dialog = page.getByRole("dialog", { name: "New report" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("radio", { name: "run" }).check();
    await expect(dialog.getByRole("combobox", { name: "Strategy" })).toBeVisible();
    await expect(dialog.getByRole("combobox", { name: "Strategy" })).toHaveValue(options.presets[0].slug);
  });
});
