import { expect, test, type Locator, type Page } from "@playwright/test";

import type { LiveResearchPayload, OptionsPayload, OverviewPayload, RunRow } from "../src/lib/api";

type ButtonSnapshot = {
  scope: string;
  name: string;
  disabled: boolean;
};

type RunsResponse = {
  items: RunRow[];
  total: number;
  page: number;
  pageSize: number;
};

const consoleTabs = [
  { tab: "Overview", heading: "Overview" },
  { tab: "Live", heading: "Live Research" },
  { tab: "Backtest", heading: "Backtest Studio" },
  { tab: "Strategy Lab", heading: "Strategy Lab" },
  { tab: "Compare", heading: "Strategy Compare" },
  { tab: "History", heading: "Run History" },
  { tab: "Universe", heading: "Universe & Data Health" },
  { tab: "Reports", heading: "Reports & Exports" },
] as const;

const navigationLabels = new Set(consoleTabs.map(({ tab }) => tab));
const journey = {
  covered: new Set<string>(),
  inventory: [] as ButtonSnapshot[],
};

function resetJourney(): void {
  journey.covered = new Set<string>();
  journey.inventory = [];
}

async function accessibleName(locator: Locator): Promise<string> {
  return locator.evaluate((node) => {
    const value = node.getAttribute("aria-label") ?? node.textContent ?? "";
    return value.replace(/\s+/g, " ").trim();
  });
}

async function recordButtons(page: Page, scope: string): Promise<void> {
  const buttons = await page.locator("button:visible").evaluateAll((nodes) =>
    nodes.map((node) => ({
      name: (node.getAttribute("aria-label") ?? node.textContent ?? "")
        .replace(/\s+/g, " ")
        .trim(),
      disabled: node instanceof HTMLButtonElement ? node.disabled : false,
    })),
  );

  for (const button of buttons) {
    if (!button.name) continue;
    journey.inventory.push({ scope, ...button });
  }
}

function cover(name: string): void {
  journey.covered.add(name);
}

async function openConsoleTab(page: Page, name: string): Promise<void> {
  const tab = page
    .getByRole("tablist", { name: "Console views" })
    .getByRole("tab", { name, exact: true });
  await tab.scrollIntoViewIfNeeded();
  await tab.click();
  cover(name);
}

async function buttonLocator(page: Page, name: string): Promise<Locator> {
  return page.getByRole("button", { name, exact: true });
}

async function clickTab(page: Page, name: string, tablistName?: string): Promise<void> {
  const scope = tablistName ? page.getByRole("tablist", { name: tablistName }) : page;
  const tab = scope.getByRole("tab", { name, exact: true });
  await tab.scrollIntoViewIfNeeded();
  await tab.click();
  cover(name);
}

async function clickRadio(page: Page, name: string, groupName: string): Promise<void> {
  const radio = page.getByRole("radiogroup", { name: groupName }).getByRole("radio", { name, exact: true });
  await radio.scrollIntoViewIfNeeded();
  await radio.click();
  cover(name);
}

async function clickButton(page: Page, name: string): Promise<void> {
  const button = await buttonLocator(page, name);
  await button.scrollIntoViewIfNeeded();
  await button.click();
  cover(name);
}

async function coverEnabledButton(page: Page, name: string): Promise<void> {
  await expect(await buttonLocator(page, name)).toBeEnabled();
  cover(name);
}

async function coverDisabledButton(page: Page, name: string): Promise<void> {
  await expect(await buttonLocator(page, name)).toBeDisabled();
  cover(name);
}

async function clickAndWaitForDownload(page: Page, name: string): Promise<void> {
  const downloadPromise = page.waitForEvent("download");
  await clickButton(page, name);
  const download = await downloadPromise;
  expect(download.suggestedFilename().length, `download from ${name}`).toBeGreaterThan(0);
}

async function getApiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `${path} returned ${response.status()}`).toBeTruthy();
  return await response.json() as T;
}

function isKnownButton(snapshot: ButtonSnapshot): boolean {
  if (navigationLabels.has(snapshot.name)) return true;
  if (snapshot.scope === "compare-modal-options") return true;

  return [
    /^View full rebalance →$/,
    /^▶ RUN NEW BACKTEST$/,
    /^COMPARE STRATEGIES$/,
    /^GENERATE REPORT$/,
    /^REFRESH LIVE DATA$/,
    /^Regenerate this run's report$/,
    /^\+ NEW RUN$/,
    /^▶ RUN BACKTEST$/,
    /^(Equity|Drawdown|Returns|Turnover|Trades)$/,
    /^View all →$/,
    /^Queue experiment$/,
    /^Open .+$/,
    /^Add strategy$/,
    /^Close add strategy$/,
    /^Cancel$/,
    /^Add$/,
    /^(1M|3M|YTD|1Y|ALL)$/,
    /^(7d|30d|90d|ytd|all|7D|30D|90D|YTD|ALL)$/,
    /^(queued|running|completed|failed|cancelled|favorited|ATLAS|Momentum|MeanRev|Carry|QUEUED|RUNNING|COMPLETED|FAILED|CANCELLED|FAVORITED|MOMENTUM|MEANREV|CARRY)$/i,
    /^(List|Grid)$/,
    /^▶ RE-RUN SELECTED$/,
    /^(Favorite|Unfavorite) .+$/,
    /^Page \d+$/,
    /^Clear filters$/,
    /^↻ FORCE REFRESH$/,
    /^(All|Weekly|Run|Compare|Universe|ALL|WEEKLY|RUN|COMPARE|UNIVERSE)$/,
    /^(MARKDOWN|PDF|PNG|CSV|DOWNLOAD ALL)$/,
    /^(Most recent|Oldest|Size|Type)$/,
    /^\+ NEW REPORT$/,
    /^Download .+ report$/,
    /^Close new report$/,
    /^Generate$/,
  ].some((pattern) => pattern.test(snapshot.name));
}

test.describe("research console full journey", () => {
  test.beforeEach(() => {
    resetJourney();
  });

  test("exercises every visible console control against the real backend", async ({ page }) => {
    test.setTimeout(180_000);

    const consoleErrors: string[] = [];
    const apiErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(`${message.location().url ?? "<console>"}: ${message.text()}`);
      }
    });
    page.on("pageerror", (error) => consoleErrors.push(error.message));
    page.on("response", (response) => {
      const url = new URL(response.url());
      if (url.pathname.startsWith("/api/") && response.status() >= 400) {
        apiErrors.push(`${response.request().method()} ${url.pathname} -> ${response.status()}`);
      }
    });

    await page.goto("/");
    for (const { tab, heading } of consoleTabs) {
      await expect(
        page.getByRole("tablist", { name: "Console views" }).getByRole("tab", { name: tab, exact: true }),
      ).toBeVisible();
      await openConsoleTab(page, tab);
      await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    }

    const overview = await getApiJson<OverviewPayload>(page, "/api/overview");
    const liveResearch = await getApiJson<LiveResearchPayload>(page, "/api/live/research");
    const options = await getApiJson<OptionsPayload>(page, "/api/options");
    const liveSpot = liveResearch.spot;
    const liveOos = liveResearch.oos;
    const liveDerivatives = liveResearch.derivatives;
    expect(liveSpot, "live spot payload").toBeTruthy();
    expect(liveOos, "live OOS payload").toBeTruthy();
    expect(liveDerivatives, "live derivatives payload").toBeTruthy();
    expect(liveSpot?.signal_date).toBeTruthy();
    expect(liveSpot?.panel_last_date).toBe(liveSpot?.signal_date);
    expect(liveSpot?.trial_id).toBeTruthy();
    expect(liveOos?.days, "live OOS tracking window").toBeGreaterThan(0);
    expect(liveDerivatives?.health.equity, "derivatives equity").toBeTruthy();
    expect(overview.equity_curve.length, "overview equity curve").toBeGreaterThan(0);
    expect(overview.selection_history.length, "overview selection history").toBeGreaterThan(0);
    expect(options.latestVerifiedDate, "latest verified date").toBeTruthy();
    if (!liveSpot || !liveOos || !liveDerivatives || !options.latestVerifiedDate) {
      throw new Error("required live research data is missing");
    }

    // Overview: real payload, charts, and every quick action.
    await openConsoleTab(page, "Overview");
    await recordButtons(page, "overview");
    await expect(
      page.getByRole("region", { name: "Current champion summary" }).getByText(overview.champion.display_name),
    ).toBeVisible();
    await expect(page.getByLabel(/equity curve/).first()).toBeVisible();

    await clickButton(page, "View full rebalance →");
    await expect(page.getByRole("heading", { name: "Run History", exact: true })).toBeVisible();
    await openConsoleTab(page, "Overview");
    await clickButton(page, "▶ RUN NEW BACKTEST");
    await expect(page.getByRole("heading", { name: "Backtest Studio", exact: true })).toBeVisible();
    await openConsoleTab(page, "Overview");
    await clickButton(page, "COMPARE STRATEGIES");
    await expect(page.getByRole("heading", { name: "Strategy Compare", exact: true })).toBeVisible();
    await openConsoleTab(page, "Overview");
    await clickButton(page, "GENERATE REPORT");
    await expect(page.getByRole("heading", { name: "Reports & Exports", exact: true })).toBeVisible();

    // Live Research: read-only refresh only; no trading action exists or is used.
    await openConsoleTab(page, "Live");
    const spotRegion = page.getByRole("region", { name: "Spot research" });
    await expect(spotRegion).toBeVisible();
    await expect(await buttonLocator(page, "REFRESH LIVE DATA")).toBeEnabled();
    await recordButtons(page, "live");
    await expect(spotRegion.getByText(liveSpot.trial_id, { exact: true })).toBeVisible();
    await expect(spotRegion.getByText(liveSpot.signal_date, { exact: true }).first()).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Current spot target weights" }).getByRole("cell", { name: /near/i }),
    ).toBeVisible();
    await expect(page.getByRole("region", { name: "Out-of-sample tracking" }).getByText(`${liveOos.days} days`)).toBeVisible();
    await expect(
      page
        .getByRole("region", { name: "Derivatives live monitor" })
        .getByText(`${liveDerivatives.health.equity?.toFixed(2)} USDT equity`),
    ).toBeVisible();

    const liveRefresh = page.waitForResponse(
      (response) => response.url().includes("/api/live/research") && response.request().method() === "GET",
    );
    await clickButton(page, "REFRESH LIVE DATA");
    expect((await liveRefresh).ok()).toBeTruthy();
    await expect(page.getByRole("region", { name: "Spot research" })).toBeVisible();

    // Backtest Studio: verified date, fixed Top-20 universe, report, run, and workspace controls.
    await openConsoleTab(page, "Backtest");
    await recordButtons(page, "backtest");
    await expect(page.getByLabel("Window end")).toHaveValue(options.latestVerifiedDate);
    await expect(page.getByText("N = 20", { exact: true })).toBeVisible();
    await expect(page.getByText("Slots · strategy-defined")).toBeVisible();
    await expect(page.getByLabel(/equity curve/).first()).toBeVisible();

    // The queue can legitimately contain an in-flight run; reports require completed artifacts.
    await coverDisabledButton(page, "Regenerate this run's report");

    const runResponse = page.waitForResponse(
      (response) => response.url().includes("/api/backtests/run") && response.request().method() === "POST",
    );
    await clickButton(page, "▶ RUN BACKTEST");
    expect((await runResponse).ok()).toBeTruthy();
    await expect(await buttonLocator(page, "▶ RUN BACKTEST")).toBeEnabled();

    for (const workspaceTab of ["Equity", "Drawdown", "Returns", "Turnover", "Trades"]) {
      await clickTab(page, workspaceTab, "Workspace views");
      await expect(
        page.getByRole("tablist", { name: "Workspace views" }).getByRole("tab", { name: workspaceTab, exact: true }),
      ).toHaveAttribute("aria-selected", "true");
    }

    await clickButton(page, "+ NEW RUN");
    await expect(page.getByLabel("Window end")).toHaveValue(options.latestVerifiedDate);
    await clickButton(page, "View all →");
    await expect(page.getByRole("heading", { name: "Run History", exact: true })).toBeVisible();

    // Strategy Lab: only the point-in-time Top-20 universe is offered.
    await openConsoleTab(page, "Strategy Lab");
    await recordButtons(page, "strategy-lab");
    await expect(page.getByText("Top 20")).toBeVisible();
    await expect(page.getByText("Top 5")).toHaveCount(0);
    await expect(page.getByText("Top 10")).toHaveCount(0);
    await expect(page.getByText("1 runs selected")).toBeVisible();

    const queueResponse = page.waitForResponse(
      (response) => response.url().includes("/api/strategy-lab/batches") && response.request().method() === "POST",
    );
    await clickButton(page, "Queue experiment");
    expect((await queueResponse).ok()).toBeTruthy();
    await expect(page.getByText(/runs queued/)).toBeVisible();
    await recordButtons(page, "strategy-lab-after-queue");

    const openRunButtons = page.getByRole("button", { name: /^Open / });
    const openRunCount = await openRunButtons.count();
    if (openRunCount > 0) {
      const openRunNames = await openRunButtons.evaluateAll((nodes) =>
        nodes.map((node) => (node.getAttribute("aria-label") ?? node.textContent ?? "").replace(/\s+/g, " ").trim()),
      );
      for (const runName of openRunNames) {
        await clickButton(page, runName);
        await expect(page.getByRole("heading", { name: "Backtest Studio", exact: true })).toBeVisible();
        await openConsoleTab(page, "Strategy Lab");
      }
    }

    // Compare: every range and the complete add-strategy modal, including disabled-at-limit options.
    await openConsoleTab(page, "Compare");
    await recordButtons(page, "compare");
    await expect(page.getByText(/\d+ selected/)).toBeVisible();
    await expect(page.getByRole("img", { name: /Equity overlay across/ })).toBeVisible();

    for (const range of ["1M", "3M", "YTD", "1Y", "ALL"]) {
      await clickTab(page, range, "Equity overlay range");
      await expect(
        page.getByRole("tablist", { name: "Equity overlay range" }).getByRole("tab", { name: range, exact: true }),
      ).toHaveAttribute("aria-selected", "true");
    }

    await clickButton(page, "Add strategy");
    let dialog = page.getByRole("dialog", { name: "Add strategy" });
    await expect(dialog).toBeVisible();
    await recordButtons(page, "compare-modal-options");

    const optionButtons = dialog.getByRole("option");
    const optionCount = await optionButtons.count();
    expect(optionCount, "strategy options in compare modal").toBeGreaterThan(0);
    for (let index = 0; index < optionCount; index += 1) {
      const option = optionButtons.nth(index);
      const optionName = await accessibleName(option);
      const ariaDisabled = await option.getAttribute("aria-disabled");
      if (ariaDisabled === "true") {
        await expect(option).toHaveAttribute("aria-disabled", "true");
        cover(optionName);
      } else {
        await option.click();
        cover(optionName);
      }
    }
    await expect(await buttonLocator(page, "Add")).toBeEnabled();
    await clickButton(page, "Add");
    await expect(dialog).toBeHidden();

    await clickButton(page, "Add strategy");
    await clickButton(page, "Cancel");
    await expect(page.getByRole("dialog", { name: "Add strategy" })).toBeHidden();

    await clickButton(page, "Add strategy");
    await clickButton(page, "Close add strategy");
    await expect(page.getByRole("dialog", { name: "Add strategy" })).toBeHidden();

    // History: favorites, every filter, both views, pagination, and a real re-run.
    await openConsoleTab(page, "History");
    await recordButtons(page, "history");
    const favoriteNames = await page
      .locator('button[aria-label^="Favorite "], button[aria-label^="Unfavorite "]')
      .evaluateAll((nodes) =>
        nodes.map((node) => (node.getAttribute("aria-label") ?? "").replace(/\s+/g, " ").trim()),
      );
    expect(favoriteNames.length, "visible run favorite buttons").toBeGreaterThan(0);
    for (const favoriteName of favoriteNames) {
      const nextName = favoriteName.startsWith("Unfavorite ")
        ? favoriteName.replace(/^Unfavorite /, "Favorite ")
        : favoriteName.replace(/^Favorite /, "Unfavorite ");
      await clickButton(page, favoriteName);
      cover(nextName);
      await clickButton(page, nextName);
    }

    for (const dateRange of ["7d", "30d", "90d", "ytd", "all"]) {
      await clickTab(page, dateRange, "Date range");
      await expect(
        page.getByRole("tablist", { name: "Date range" }).getByRole("tab", { name: dateRange, exact: true }),
      ).toHaveAttribute("aria-selected", "true");
    }

    const historyChips = [
      "queued",
      "running",
      "completed",
      "failed",
      "cancelled",
      "favorited",
      "ATLAS",
      "Momentum",
      "MeanRev",
      "Carry",
    ];
    for (const chip of historyChips) {
      await clickButton(page, chip);
    }
    await recordButtons(page, "history-filtered");
    const search = page.getByRole("searchbox", { name: "Search runs" });
    await search.fill("__no_matching_atlas20_run__");
    await expect(page.getByText("No runs match these filters")).toBeVisible();
    const clearFilters = await buttonLocator(page, "Clear filters");
    await expect(clearFilters).toBeVisible();
    await clickButton(page, "Clear filters");
    await expect(page.getByRole("button", { name: "queued", exact: true })).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByRole("button", { name: "Carry", exact: true })).toHaveAttribute("aria-pressed", "false");
    await expect(search).toHaveValue("");

    const completedRuns = await getApiJson<RunsResponse>(
      page,
      "/api/runs?q=&chips=completed&dateRange=all&page=1&pageSize=50",
    );
    const completedRun = completedRuns.items.find((run) => run.strategy !== "universe_refresh" && run.return_pct != null);
    expect(completedRun, "completed backtest available for report regeneration").toBeTruthy();
    if (!completedRun) throw new Error("no completed backtest available");
    await search.fill(completedRun.run_id);
    await expect(page.locator(`[data-run-id="${completedRun.run_id}"]`)).toBeVisible();

    await clickRadio(page, "Grid", "View mode");
    await expect(page.getByTestId("run-history-grid")).toBeVisible();
    await clickRadio(page, "List", "View mode");
    await search.clear();
    await clickTab(page, "all", "Date range");
    await expect(await buttonLocator(page, "Page 2")).toBeVisible();

    const pageNames = await page
      .locator('button[aria-label^="Page "]')
      .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label") ?? ""));
    for (const pageName of pageNames) {
      const pageButton = await buttonLocator(page, pageName);
      const isCurrentPage = (await pageButton.getAttribute("aria-current")) === "page";
      if (isCurrentPage) {
        await coverDisabledButton(page, pageName);
      } else {
        await expect(pageButton).toBeEnabled();
        await clickButton(page, pageName);
        if (pageName !== "Page 1") await clickButton(page, "Page 1");
      }
    }

    await coverDisabledButton(page, "▶ RE-RUN SELECTED");
    await search.fill(completedRun.run_id);
    const completedRunRow = page.locator(`[data-run-id="${completedRun.run_id}"]`);
    await expect(completedRunRow).toBeVisible();
    await completedRunRow.scrollIntoViewIfNeeded();
    await completedRunRow.click();
    await coverEnabledButton(page, "▶ RE-RUN SELECTED");
    await clickButton(page, "▶ RE-RUN SELECTED");
    await expect(page.getByRole("heading", { name: "Backtest Studio", exact: true })).toBeVisible();

    const completedRegenerateResponse = page.waitForResponse(
      (response) => response.url().includes("/api/reports/generate") && response.request().method() === "POST",
    );
    await coverEnabledButton(page, "Regenerate this run's report");
    await clickButton(page, "Regenerate this run's report");
    expect((await completedRegenerateResponse).ok()).toBeTruthy();

    // Universe: a real queued refresh and its status transition.
    await openConsoleTab(page, "Universe");
    await recordButtons(page, "universe");
    await expect(page.getByRole("region", { name: "Universe composition timeline" })).toBeVisible();
    const refreshResponse = page.waitForResponse(
      (response) => response.url().includes("/api/universe/refresh") && response.request().method() === "POST",
    );
    await clickButton(page, "↻ FORCE REFRESH");
    const refresh = await refreshResponse;
    expect(refresh.ok()).toBeTruthy();
    const refreshPayload = await refresh.json() as { run_id: string };
    await expect(
      page.getByText(new RegExp(`Refresh ${refreshPayload.run_id} (queued|running|completed)`)),
    ).toBeVisible();

    // Reports: filters, sort, modal disabled/enabled states, generation, and every download format.
    await openConsoleTab(page, "Reports");
    await recordButtons(page, "reports");
    for (const typeFilter of ["All", "Weekly", "Run", "Compare", "Universe"]) {
      await clickTab(page, typeFilter, "Report type filter");
      await expect(
        page.getByRole("tablist", { name: "Report type filter" }).getByRole("tab", { name: typeFilter, exact: true }),
      ).toHaveAttribute("aria-selected", "true");
    }
    await clickTab(page, "All", "Report type filter");
    for (const sort of ["Most recent", "Oldest", "Size", "Type"]) {
      await clickTab(page, sort, "Archive sort");
      await expect(
        page.getByRole("tablist", { name: "Archive sort" }).getByRole("tab", { name: sort, exact: true }),
      ).toHaveAttribute("aria-selected", "true");
    }
    await clickTab(page, "Most recent", "Archive sort");

    await clickButton(page, "+ NEW REPORT");
    dialog = page.getByRole("dialog", { name: "New report" });
    await expect(dialog).toBeVisible();
    await recordButtons(page, "reports-modal");
    await dialog.getByRole("checkbox", { name: "markdown", exact: true }).uncheck();
    await coverDisabledButton(page, "Generate");
    await dialog.getByRole("checkbox", { name: "markdown", exact: true }).check();
    await coverEnabledButton(page, "Generate");
    await clickButton(page, "Cancel");
    await expect(dialog).toBeHidden();

    await clickButton(page, "+ NEW REPORT");
    await clickButton(page, "Close new report");
    await expect(page.getByRole("dialog", { name: "New report" })).toBeHidden();

    await clickButton(page, "+ NEW REPORT");
    const generateResponse = page.waitForResponse(
      (response) => response.url().includes("/api/reports/generate") && response.request().method() === "POST",
    );
    await clickButton(page, "Generate");
    expect((await generateResponse).ok()).toBeTruthy();
    await expect(page.getByRole("dialog", { name: "New report" })).toBeHidden();

    await recordButtons(page, "reports-after-generate");
    for (const digestFormat of ["MARKDOWN", "PDF", "PNG", "CSV", "DOWNLOAD ALL"]) {
      await clickAndWaitForDownload(page, digestFormat);
    }

    const reportDownloadNames = await page
      .locator('button[aria-label^="Download "]')
      .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label") ?? "").filter(Boolean));
    expect(reportDownloadNames.length, "visible report download buttons").toBeGreaterThan(0);
    for (const reportDownloadName of reportDownloadNames) {
      await clickAndWaitForDownload(page, reportDownloadName);
    }

    await page.waitForTimeout(500);
    expect(apiErrors, "API responses with status >= 400").toEqual([]);
    expect(consoleErrors, "browser console/page errors").toEqual([]);

    const unknownButtons = journey.inventory.filter((button) => !isKnownButton(button));
    expect(unknownButtons, "unknown buttons found in visible inventory").toEqual([]);
    const uncoveredButtons = journey.inventory.filter((button) => !journey.covered.has(button.name));
    expect(uncoveredButtons, "buttons not clicked or explicitly state-covered").toEqual([]);
    expect(journey.inventory.length, "visible buttons recorded").toBeGreaterThan(0);
  });
});
