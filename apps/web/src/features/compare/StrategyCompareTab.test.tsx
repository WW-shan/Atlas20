import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { StrategyCompareTab } from "./StrategyCompareTab";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    getCompare: vi.fn(),
    getOptions: vi.fn(),
  };
});

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function compareFor(ids: string[]): api.ComparePayload {
  const metricKeys = Object.keys(api.fallbackCompare.metrics) as api.CompareMetricKey[];
  const metrics = {} as api.ComparePayload["metrics"];
  for (const key of metricKeys) {
    metrics[key] = Object.fromEntries(
      ids.map((id, index) => [id, index === 0 ? 1.5 : 0.8 - index * 0.1]),
    );
  }
  return {
    equity: api.fallbackCompare.equity.map((point, pointIndex) => ({
      ts: point.ts,
      values: Object.fromEntries(ids.map((id, index) => [id, pointIndex * (index + 1)])),
    })),
    metrics,
    overlap: {
      symbols: ids,
      matrix: ids.map((_, row) => ids.map((__, column) => (row === column ? 1 : 0.25))),
      sharedHoldings: api.fallbackCompare.overlap.sharedHoldings,
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
  vi.mocked(api.getCompare).mockImplementation((ids) => Promise.resolve(compareFor(ids)));
  vi.mocked(api.getOptions).mockResolvedValue(api.fallbackOptions);
});

describe("StrategyCompareTab", () => {
  it("renders 3 default strategy chips", () => {
    renderWithQuery(<StrategyCompareTab />);
    const list = screen.getByRole("list", { name: "Selected strategies" });
    const items = list.querySelectorAll("[role='listitem']");
    expect(items.length).toBe(3);
    expect(screen.getAllByText("ATLAS Adaptive v3").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Momentum Top-10").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Mean Reversion v2").length).toBeGreaterThanOrEqual(1);
  });

  it("renders + ADD STRATEGY dashed chip", () => {
    renderWithQuery(<StrategyCompareTab />);
    expect(screen.getByRole("button", { name: "Add strategy" })).toBeInTheDocument();
  });

  it("renders 8 metric rows in ComparisonTable", () => {
    renderWithQuery(<StrategyCompareTab />);
    const table = screen.getByRole("table", { name: "Metric comparison table" });
    const bodyRows = table.querySelectorAll("tbody tr");
    expect(bodyRows.length).toBe(8);
  });

  it("marks best CAGR cell as ATLAS via data-best", () => {
    const { container } = renderWithQuery(<StrategyCompareTab />);
    const bestCagr = container.querySelector('[data-metric="cagr"][data-best="true"]');
    expect(bestCagr).not.toBeNull();
    expect(bestCagr?.getAttribute("data-strategy")).toBe("atlas");
  });

  it("marks best Max DD cell as MeanRev (lower-is-better)", () => {
    const { container } = renderWithQuery(<StrategyCompareTab />);
    const bestDd = container.querySelector('[data-metric="max_dd"][data-best="true"]');
    expect(bestDd?.getAttribute("data-strategy")).toBe("meanrev");
  });

  it("renders Jaccard heatmap with 9 cells (3x3)", () => {
    const { container } = renderWithQuery(<StrategyCompareTab />);
    const heatmap = screen.getByRole("table", { name: "Jaccard holdings overlap heatmap" });
    const cells = heatmap.querySelectorAll("[data-row]");
    expect(cells.length).toBe(9);
    // 3 diagonal cells
    const diag = container.querySelectorAll('[data-diagonal="true"]');
    expect(diag.length).toBe(3);
  });

  it("renders top shared holdings with 5 rows", () => {
    renderWithQuery(<StrategyCompareTab />);
    const list = screen.getByRole("list", { name: "Top shared holdings" });
    const items = list.querySelectorAll("[role='listitem']");
    expect(items.length).toBe(5);
    expect(screen.getByText("SOL")).toBeInTheDocument();
    expect(screen.getByText("TIA")).toBeInTheDocument();
  });

  it("range tablist starts at YTD active", () => {
    renderWithQuery(<StrategyCompareTab />);
    const ytdTab = screen.getByRole("tab", { name: "YTD" });
    expect(ytdTab.getAttribute("aria-selected")).toBe("true");
  });

  it("clicking 1Y range updates active range tab", () => {
    renderWithQuery(<StrategyCompareTab />);
    fireEvent.click(screen.getByRole("tab", { name: "1Y" }));
    expect(screen.getByRole("tab", { name: "1Y" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tab", { name: "YTD" }).getAttribute("aria-selected")).toBe("false");
  });

  it("equity overlay chart has accessible name with range", () => {
    renderWithQuery(<StrategyCompareTab />);
    expect(screen.getByRole("img", { name: /Equity overlay across 3 strategies, range YTD/ })).toBeInTheDocument();
  });

  it("opens add strategy modal with presets from getOptions", async () => {
    renderWithQuery(<StrategyCompareTab />);

    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));

    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    expect(dialog).toHaveAttribute("aria-labelledby", "add-strategy-modal-title");
    expect(within(dialog).getByRole("heading", { name: "Add strategy" })).toHaveAttribute("id", "add-strategy-modal-title");
    expect(within(dialog).getByRole("searchbox", { name: "Search strategies" })).toBeInTheDocument();
    const listbox = within(dialog).getByRole("listbox", { name: "Available strategies" });
    expect(within(listbox).getByRole("option", { name: "ATLAS Adaptive v3" })).toHaveAttribute("aria-selected", "true");
    expect(within(listbox).getByRole("option", { name: "ATLAS Adaptive v2" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Carry Top-5" })).toBeInTheDocument();
  });

  it("adds selected strategies as compare columns and refetches with new ids", async () => {
    renderWithQuery(<StrategyCompareTab />);

    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));
    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    fireEvent.click(within(dialog).getByRole("option", { name: "ATLAS Adaptive v2" }));
    fireEvent.click(within(dialog).getByRole("option", { name: "Carry Top-5" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add strategy" })).not.toBeInTheDocument());
    expect(screen.getByRole("columnheader", { name: "ATLAS Adaptive v2" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Carry Top-5" })).toBeInTheDocument();
    await waitFor(() => expect(vi.mocked(api.getCompare).mock.calls.at(-1)?.[0]).toHaveLength(5));
    expect(new URLSearchParams(window.location.search).get("ids")?.split(",")).toHaveLength(5);
  });

  it("canceling add strategy preserves the previous compare selection", async () => {
    renderWithQuery(<StrategyCompareTab />);

    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));
    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    fireEvent.click(within(dialog).getByRole("option", { name: "ATLAS Adaptive v2" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add strategy" })).not.toBeInTheDocument());
    expect(screen.queryByRole("columnheader", { name: "ATLAS Adaptive v2" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Strategy selection" })).toHaveTextContent("3 selected");
  });

  it("keeps fallback compare data visible while the compare query is loading", () => {
    vi.mocked(api.getCompare).mockImplementation(() => new Promise<api.ComparePayload>(() => {}));

    renderWithQuery(<StrategyCompareTab />);

    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Metric comparison table" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "ATLAS Adaptive v3" })).toBeInTheDocument();
  });

  it("renders compare error banner and retries the compare query", async () => {
    vi.mocked(api.getCompare)
      .mockRejectedValueOnce(new Error("compare failed"))
      .mockResolvedValueOnce(compareFor(["atlas", "momentum", "meanrev"]));

    renderWithQuery(<StrategyCompareTab />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load strategy comparison");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(api.getCompare).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("table", { name: "Metric comparison table" })).toBeInTheDocument();
  });

  it("renders compare empty state when no strategies are selected", () => {
    renderWithQuery(<StrategyCompareTab initialSelections={[]} />);

    expect(screen.getByText("No strategies selected")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Metric comparison table" })).not.toBeInTheDocument();
  });

  it("keeps fallback strategy options visible while options are loading", async () => {
    vi.mocked(api.getOptions).mockImplementation(() => new Promise<api.OptionsPayload>(() => {}));

    renderWithQuery(<StrategyCompareTab />);
    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));

    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    expect(within(dialog).getByRole("option", { name: "ATLAS Adaptive v2" })).toBeInTheDocument();
  });
});
