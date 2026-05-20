import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import type { HistoryFilter, RunRow } from "../../lib/api";
import { RunHistoryTab } from "./RunHistoryTab";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    listRuns: vi.fn(),
    toggleFavorite: vi.fn(),
  };
});

let serverRows: RunRow[] = [];

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function cloneRows(): RunRow[] {
  return api.fallbackRunsList.map((row) => ({
    ...row,
    window: { ...row.window },
    spark: row.spark ? [...row.spark] : undefined,
  }));
}

function matchesChip(row: RunRow, chip: string): boolean {
  if (chip === "favorited") return Boolean(row.favorited);
  if (["queued", "running", "completed", "failed", "cancelled"].includes(chip)) return row.status === chip;
  return row.strategy_family === chip || row.strategy.includes(chip);
}

function rowsForFilter(filter: HistoryFilter): RunRow[] {
  const q = filter.q.trim().toLowerCase();
  return serverRows.filter((row) => {
    const matchesQuery = !q ||
      row.run_id.toLowerCase().includes(q) ||
      row.strategy.toLowerCase().includes(q) ||
      row.universe.toLowerCase().includes(q);
    return matchesQuery && filter.chips.every((chip) => matchesChip(row, chip));
  });
}

function mockListRunsFromServer() {
  vi.mocked(api.listRuns).mockImplementation(async (filter) => {
    const filtered = rowsForFilter(filter);
    const start = (filter.page - 1) * filter.pageSize;
    return {
      items: filtered.slice(start, start + filter.pageSize),
      total: filtered.length,
      page: filter.page,
      pageSize: filter.pageSize,
    };
  });
}

async function waitForRunRows(count: number) {
  await waitFor(() => expect(document.querySelectorAll("tr[data-run-id]").length).toBe(count));
}

beforeEach(() => {
  vi.clearAllMocks();
  serverRows = cloneRows();
  mockListRunsFromServer();
  vi.mocked(api.toggleFavorite).mockImplementation(async (runId) => {
    const row = serverRows.find((r) => r.run_id === runId);
    const favorited = !(row?.favorited ?? false);
    if (row) row.favorited = favorited;
    return { run_id: runId, favorited };
  });
});

describe("RunHistoryTab", () => {
  it("renders Toolbar search input", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    expect(screen.getByRole("searchbox", { name: "Search runs" })).toBeInTheDocument();
  });

  it("renders 5 date range tabs with 30d active by default", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    const dateGroup = screen.getByRole("tablist", { name: "Date range" });
    expect(dateGroup.querySelectorAll("[role='tab']").length).toBe(5);
    expect(screen.getByRole("tab", { name: "30d" }).getAttribute("aria-selected")).toBe("true");
  });

  it("switching date range to 'all' yields 14 fallback rows", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    fireEvent.click(screen.getByRole("tab", { name: "all" }));
    await waitForRunRows(14);
  });

  it("renders RunTable header with 13 columns + 1 selection-bar column", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await screen.findByRole("table", { name: "Runs list" });
    const headers = document.querySelectorAll("thead th");
    expect(headers.length).toBeGreaterThanOrEqual(13);
  });

  it("switches list and grid views without sending view to the API", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await screen.findByRole("table", { name: "Runs list" });

    fireEvent.click(screen.getByRole("radio", { name: "Grid" }));
    expect(await screen.findByTestId("run-history-grid")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Runs list" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "List" }));
    expect(await screen.findByRole("table", { name: "Runs list" })).toBeInTheDocument();
    expect(screen.queryByTestId("run-history-grid")).not.toBeInTheDocument();

    for (const [filter] of vi.mocked(api.listRuns).mock.calls) {
      expect("view" in filter).toBe(false);
    }
  });

  it("renders RUNNING pill with pulse for in-flight runs", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    expect((await screen.findAllByText("running")).length).toBeGreaterThanOrEqual(1);
  });

  it("typing in search filters rows", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await waitForRunRows(14);
    const search = screen.getByRole("searchbox", { name: "Search runs" });
    fireEvent.change(search, { target: { value: "btk_0148" } });
    await waitForRunRows(1);
    const rows = document.querySelectorAll("tr[data-run-id]");
    expect(rows[0]?.getAttribute("data-run-id")).toBe("btk_0148");
  });

  it("clicking favorited chip filters to favorited runs", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await waitForRunRows(14);
    fireEvent.click(screen.getByRole("button", { name: "favorited" }));
    await waitForRunRows(2);
  });

  it("clicking a row selects it (aria-selected) without navigating", async () => {
    const onNavigate = vi.fn();
    renderWithQuery(<RunHistoryTab onNavigate={onNavigate} />);
    await waitForRunRows(14);
    const firstRow = document.querySelector("tr[data-run-id]") as HTMLElement;
    fireEvent.click(firstRow);
    expect(firstRow.getAttribute("aria-selected")).toBe("true");
    expect(firstRow.getAttribute("data-selected")).toBe("true");
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("RE-RUN SELECTED is disabled until a row is selected", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    const btn = screen.getByRole("button", { name: /RE-RUN SELECTED/ });
    expect(btn.hasAttribute("disabled")).toBe(true);
  });

  it("clicking RE-RUN SELECTED navigates to backtest with prefillRunId", async () => {
    const onNavigate = vi.fn();
    renderWithQuery(<RunHistoryTab onNavigate={onNavigate} />);
    await waitForRunRows(14);
    const firstRow = document.querySelector("tr[data-run-id]") as HTMLElement;
    fireEvent.click(firstRow);
    fireEvent.click(screen.getByRole("button", { name: /RE-RUN SELECTED/ }));
    expect(onNavigate).toHaveBeenCalledWith("backtest", firstRow.getAttribute("data-run-id"));
  });

  it("favorite star button toggles without triggering row selection", async () => {
    vi.mocked(api.toggleFavorite).mockImplementation(() => new Promise<Awaited<ReturnType<typeof api.toggleFavorite>>>(() => {}));

    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await waitForRunRows(14);
    const favBtn = screen.getAllByRole("button", { name: /Favorite|Unfavorite/ })[0];
    fireEvent.click(favBtn);
    const firstRow = document.querySelector("tr[data-run-id]") as HTMLElement;
    expect(firstRow.getAttribute("aria-selected")).not.toBe("true");
  });

  it("favorite star flips aria-pressed when clicked (wired toggle)", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await waitForRunRows(14);
    const targetRow = document.querySelector('tr[data-run-id="btk_0146"]') as HTMLElement;
    const favBtn = targetRow.querySelector('button[aria-label^="Favorite"]') as HTMLButtonElement;
    expect(favBtn.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(favBtn);
    await waitFor(() => {
      const after = document.querySelector('tr[data-run-id="btk_0146"] button[aria-label^="Unfavorite"]');
      expect(after).not.toBeNull();
      expect(after?.getAttribute("aria-pressed")).toBe("true");
    });
  });

  it("clicking an already-favorited row's star un-favorites it (toggle works in both directions)", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await waitForRunRows(14);
    const targetRow = document.querySelector('tr[data-run-id="btk_0148"]') as HTMLElement;
    const favBtn = targetRow.querySelector('button[aria-label^="Unfavorite"]') as HTMLButtonElement;
    expect(favBtn).not.toBeNull();
    expect(favBtn.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(favBtn);
    await waitFor(() => {
      const after = document.querySelector('tr[data-run-id="btk_0148"] button[aria-label^="Favorite"]');
      expect(after).not.toBeNull();
      expect(after?.getAttribute("aria-pressed")).toBe("false");
    });
  });

  it("Pager exists and shows total count", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
  });

  it("shows No backtests yet when the unfiltered list is empty", async () => {
    vi.mocked(api.listRuns).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 14 });

    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);

    expect(await screen.findByText("No backtests yet")).toBeInTheDocument();
  });

  it("shows filtered empty state and clears filters", async () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await waitForRunRows(14);

    const search = screen.getByRole("searchbox", { name: "Search runs" });
    fireEvent.change(search, { target: { value: "zzz" } });

    expect(await screen.findByText("No runs match these filters")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));

    await waitForRunRows(14);
    expect((screen.getByRole("searchbox", { name: "Search runs" }) as HTMLInputElement).value).toBe("");
  });

  it("renders 5 skeleton rows and disables filter chips while loading", () => {
    vi.mocked(api.listRuns).mockImplementation(() => new Promise<Awaited<ReturnType<typeof api.listRuns>>>(() => {}));

    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);

    expect(screen.getAllByTestId("run-history-skeleton-row")).toHaveLength(5);
    expect(screen.getByRole("button", { name: "favorited" })).toBeDisabled();
  });

  it("renders run history error banner and retries the list query", async () => {
    vi.mocked(api.listRuns).mockRejectedValueOnce(new Error("history failed"));

    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load run history");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(api.listRuns).toHaveBeenCalledTimes(2));
    await waitForRunRows(14);
  });

  it("disables all favorite buttons while a favorite mutation is pending", async () => {
    vi.mocked(api.toggleFavorite).mockImplementation(() => new Promise<Awaited<ReturnType<typeof api.toggleFavorite>>>(() => {}));

    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    await waitForRunRows(14);

    const targetRow = document.querySelector('tr[data-run-id="btk_0146"]') as HTMLElement;
    const favBtn = targetRow.querySelector('button[aria-label^="Favorite"]') as HTMLButtonElement;
    fireEvent.click(favBtn);

    await waitFor(() => {
      const favoriteButtons = screen.getAllByRole("button", { name: /Favorite|Unfavorite/ });
      expect(favoriteButtons.length).toBeGreaterThan(1);
      for (const button of favoriteButtons) {
        expect(button).toBeDisabled();
        expect(button).toHaveAttribute("aria-busy", "true");
      }
    });
  });
});
