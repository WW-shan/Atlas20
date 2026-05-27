import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { StrategyCompareTab } from "./StrategyCompareTab";

const TEST_SELECTIONS = [
  { id: "atlas", label: "ATLAS v3", tone: "gold" as const },
  { id: "momentum", label: "Momentum", tone: "violet" as const },
  { id: "meanrev", label: "MeanRev", tone: "cyan" as const },
];

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
    strategies: ids.map((id) => ({ strategy: id, display_name: id })),
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
    data_source: "real",
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
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    const list = screen.getByRole("list", { name: "Selected strategies" });
    const items = list.querySelectorAll("[role='listitem']");
    expect(items.length).toBe(3);
    expect(screen.getAllByText("ATLAS v3").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Momentum").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("MeanRev").length).toBeGreaterThanOrEqual(1);
  });

  it("renders + ADD STRATEGY dashed chip", () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    expect(screen.getByRole("button", { name: "Add strategy" })).toBeInTheDocument();
  });

  it("renders 8 metric rows in ComparisonTable", () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    const table = screen.getByRole("table", { name: "Metric comparison table" });
    const bodyRows = table.querySelectorAll("tbody tr");
    expect(bodyRows.length).toBe(8);
  });

  it("marks best CAGR cell as ATLAS via data-best", () => {
    const { container } = renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    const bestCagr = container.querySelector('[data-metric="cagr"][data-best="true"]');
    expect(bestCagr).not.toBeNull();
    expect(bestCagr?.getAttribute("data-strategy")).toBe("atlas");
  });

  it("marks best Max DD cell as MeanRev (lower-is-better)", () => {
    const { container } = renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    const bestDd = container.querySelector('[data-metric="max_dd"][data-best="true"]');
    expect(bestDd?.getAttribute("data-strategy")).toBe("meanrev");
  });

  it("renders Jaccard heatmap with 9 cells (3x3)", () => {
    const { container } = renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    const heatmap = screen.getByRole("table", { name: "Jaccard holdings overlap heatmap" });
    const cells = heatmap.querySelectorAll("[data-row]");
    expect(cells.length).toBe(9);
    // 3 diagonal cells
    const diag = container.querySelectorAll('[data-diagonal="true"]');
    expect(diag.length).toBe(3);
  });

  it("renders top shared holdings with 5 rows", () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    const list = screen.getByRole("list", { name: "Top shared holdings" });
    const items = list.querySelectorAll("[role='listitem']");
    expect(items.length).toBe(5);
    expect(screen.getByText("SOL")).toBeInTheDocument();
    expect(screen.getByText("TIA")).toBeInTheDocument();
  });

  it("range tablist starts at YTD active", () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    const ytdTab = screen.getByRole("tab", { name: "YTD" });
    expect(ytdTab.getAttribute("aria-selected")).toBe("true");
  });

  it("clicking 1Y range updates active range tab", () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    fireEvent.click(screen.getByRole("tab", { name: "1Y" }));
    expect(screen.getByRole("tab", { name: "1Y" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tab", { name: "YTD" }).getAttribute("aria-selected")).toBe("false");
  });

  it("equity overlay chart has accessible name with range", () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    expect(screen.getByRole("img", { name: /Equity overlay across 3 strategies, range YTD/ })).toBeInTheDocument();
  });

  it("opens add strategy modal with presets from getOptions", async () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);

    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));

    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    expect(dialog).toHaveAttribute("aria-labelledby", "add-strategy-modal-title");
    expect(within(dialog).getByRole("heading", { name: "Add strategy" })).toHaveAttribute("id", "add-strategy-modal-title");
    expect(within(dialog).getByRole("searchbox", { name: "Search strategies" })).toBeInTheDocument();
    const listbox = within(dialog).getByRole("listbox", { name: "Available strategies" });
    expect(within(listbox).getByRole("option", { name: "ATLAS v3" })).toHaveAttribute("aria-selected", "true");
    expect(within(listbox).getByRole("option", { name: "Base Config" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Five Year 2020 2024" })).toBeInTheDocument();
  });

  it("shows full strategy options in the add strategy modal", async () => {
    vi.mocked(api.getOptions).mockResolvedValue({
      ...api.fallbackOptions,
      presets: [{ slug: "ALPHA_PRESET", display_name: "Alpha Preset" }],
      strategies: [{ strategy: "OMEGA_REAL_STRATEGY", display_name: "Omega Real Strategy" }],
    });
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);

    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));

    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    expect(await within(dialog).findByRole("option", { name: "Omega Real Strategy" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("option", { name: "Omega Real Strategy" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(vi.mocked(api.getCompare).mock.calls.at(-1)?.[0]).toContain("OMEGA_REAL_STRATEGY");
    });
  });

  it("adds selected strategies as compare columns and refetches with new ids", async () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);

    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));
    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    fireEvent.click(within(dialog).getByRole("option", { name: "Base Config" }));
    fireEvent.click(within(dialog).getByRole("option", { name: "Five Year 2020 2024" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Add" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add strategy" })).not.toBeInTheDocument());
    expect(screen.getByRole("columnheader", { name: "Base Config" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Five Year 2020 2024" })).toBeInTheDocument();
    await waitFor(() => expect(vi.mocked(api.getCompare).mock.calls.at(-1)?.[0]).toHaveLength(5));
    expect(new URLSearchParams(window.location.search).get("ids")?.split(",")).toHaveLength(5);
  });

  it("canceling add strategy preserves the previous compare selection", async () => {
    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);

    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));
    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    fireEvent.click(within(dialog).getByRole("option", { name: "Base Config" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add strategy" })).not.toBeInTheDocument());
    expect(screen.queryByRole("columnheader", { name: "Base Config" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Strategy selection" })).toHaveTextContent("3 selected");
  });

  it("shows loading state while the compare query is loading", () => {
    vi.mocked(api.getCompare).mockImplementation(() => new Promise<api.ComparePayload>(() => {}));

    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);

    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });

  it("renders compare error banner and retries the compare query", async () => {
    vi.mocked(api.getCompare)
      .mockRejectedValueOnce(new Error("compare failed"))
      .mockResolvedValueOnce(compareFor(["atlas", "momentum", "meanrev"]));

    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);

    expect(await screen.findByText("Unable to load strategy comparison.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(api.getCompare).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("table", { name: "Metric comparison table" })).toBeInTheDocument();
  });

  it("renders compare empty state when no strategies are selected", () => {
    renderWithQuery(<StrategyCompareTab initialSelections={[]} />);

    expect(screen.getByText("No strategies selected")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Metric comparison table" })).not.toBeInTheDocument();
  });

  it("seeds 3 chips from real /api/options presets when no initialSelections prop is given", async () => {
    vi.mocked(api.getOptions).mockResolvedValue({
      ...api.fallbackOptions,
      presets: [
        { slug: "ETH Benchmark · Bull Only", display_name: "ETH Benchmark · Bull Only" },
        { slug: "BTC_BH__always_on", display_name: "BTC Benchmark" },
        { slug: "TOP20_MOM_top4_weekly__always_on", display_name: "Momentum Rotation · Weekly" },
        { slug: "TOP20_SECTOR_top3_monthly__always_on", display_name: "Sector Rotation · Monthly" },
      ],
    });

    renderWithQuery(<StrategyCompareTab />);

    await waitFor(() => {
      const list = screen.getByRole("list", { name: "Selected strategies" });
      expect(list.querySelectorAll("[role='listitem']").length).toBe(3);
    });

    expect(screen.getAllByText("ETH Benchmark · Bull Only").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("BTC Benchmark").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Momentum Rotation · Weekly").length).toBeGreaterThanOrEqual(1);
    // Ensure /api/compare was called with the EXACT real names (no slugification).
    await waitFor(() => {
      const lastCall = vi.mocked(api.getCompare).mock.calls.at(-1);
      expect(lastCall?.[0]).toEqual([
        "ETH Benchmark · Bull Only",
        "BTC_BH__always_on",
        "TOP20_MOM_top4_weekly__always_on",
      ]);
    });
  });

  it("does not reseed selections when /api/options refetches with a different list", async () => {
    vi.mocked(api.getOptions).mockResolvedValue({
      ...api.fallbackOptions,
      presets: [
        { slug: "ETH Benchmark · Bull Only", display_name: "ETH Benchmark · Bull Only" },
        { slug: "BTC_BH__always_on", display_name: "BTC Benchmark" },
        { slug: "TOP20_MOM_top4_weekly__always_on", display_name: "Momentum Rotation · Weekly" },
      ],
    });

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><StrategyCompareTab /></QueryClientProvider>);

    await waitFor(() => {
      expect(screen.getAllByText("ETH Benchmark · Bull Only").length).toBeGreaterThanOrEqual(1);
    });
    const firstCallCount = vi.mocked(api.getOptions).mock.calls.length;

    // Swap the getOptions mock to return a DIFFERENT preset list, then force
    // React Query to actually refetch by invalidating the cached entry. The
    // previous test only mocked a second response and waited for a timer
    // without triggering a fetch -- queryFn was never re-invoked, so the
    // "no reseed" assertion was trivial. Now we exercise the real refetch
    // path and verify seededRef prevents the chips from being clobbered.
    vi.mocked(api.getOptions).mockResolvedValue({
      ...api.fallbackOptions,
      presets: [
        { slug: "TOP20_SECTOR_top4_monthly__bull_only", display_name: "Sector Rotation · Monthly · Bull Only" },
        { slug: "ETH_BH__always_on", display_name: "ETH Benchmark" },
        { slug: "BTC_BH__bull_only", display_name: "BTC Benchmark · Bull Only" },
      ],
    });
    await client.invalidateQueries({ queryKey: ["options"] });
    await waitFor(() => {
      expect(vi.mocked(api.getOptions).mock.calls.length).toBeGreaterThan(firstCallCount);
    });

    // The originally seeded chips MUST persist; reseeding from the new preset
    // list would clobber any user edits made between the two fetches.
    expect(screen.getAllByText("ETH Benchmark · Bull Only").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("TOP20_SECTOR_top4_monthly__bull_only")).not.toBeInTheDocument();
  });

  it("keeps fallback strategy options visible while options are loading", async () => {
    vi.mocked(api.getOptions).mockImplementation(() => new Promise<api.OptionsPayload>(() => {}));

    renderWithQuery(<StrategyCompareTab initialSelections={TEST_SELECTIONS} />);
    fireEvent.click(screen.getByRole("button", { name: "Add strategy" }));

    const dialog = await screen.findByRole("dialog", { name: "Add strategy" });
    expect(within(dialog).getByRole("option", { name: "Base Config" })).toBeInTheDocument();
  });
});
