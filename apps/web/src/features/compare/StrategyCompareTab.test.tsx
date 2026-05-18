import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StrategyCompareTab } from "./StrategyCompareTab";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("StrategyCompareTab", () => {
  it("renders 3 default strategy chips", () => {
    renderWithQuery(<StrategyCompareTab />);
    const list = screen.getByRole("list", { name: "Selected strategies" });
    const items = list.querySelectorAll("[role='listitem']");
    expect(items.length).toBe(3);
    expect(screen.getAllByText("ATLAS Adaptive v3").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Momentum Family").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Mean Reversion").length).toBeGreaterThanOrEqual(1);
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
    const heatmap = screen.getByRole("img", { name: "Jaccard holdings overlap heatmap" });
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
});
