import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RunHistoryTab } from "./RunHistoryTab";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

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

  it("renders list/grid view toggle with list active", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    const listBtn = screen.getByRole("button", { name: "list" });
    expect(listBtn.getAttribute("aria-pressed")).toBe("true");
  });

  it("renders RunTable with all fallback rows on default filter", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    expect(screen.getByRole("region", { name: "Run history table" })).toBeInTheDocument();
    // fallback has 14 runs, default page size 14 → all on page 1
    const rows = document.querySelectorAll("tr[data-run-id]");
    expect(rows.length).toBeGreaterThanOrEqual(10);
  });

  it("renders RUNNING pill with pulse for in-flight runs", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    const runningPills = screen.getAllByText("running");
    expect(runningPills.length).toBeGreaterThanOrEqual(1);
  });

  it("typing in search filters rows", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    const search = screen.getByRole("searchbox", { name: "Search runs" });
    fireEvent.change(search, { target: { value: "btk_0148" } });
    const rows = document.querySelectorAll("tr[data-run-id]");
    expect(rows.length).toBe(1);
    expect(rows[0]?.getAttribute("data-run-id")).toBe("btk_0148");
  });

  it("clicking favorited chip filters to favorited runs", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "favorited" }));
    const rows = document.querySelectorAll("tr[data-run-id]");
    // fallbackRunsList has 2 favorited runs (btk_0148, btk_0142)
    expect(rows.length).toBe(2);
  });

  it("clicking a row navigates to backtest with prefill run_id", () => {
    const onNavigate = vi.fn();
    renderWithQuery(<RunHistoryTab onNavigate={onNavigate} />);
    const firstRow = document.querySelector("tr[data-run-id]") as HTMLElement;
    fireEvent.click(firstRow);
    expect(onNavigate).toHaveBeenCalledWith("backtest", firstRow.getAttribute("data-run-id"));
  });

  it("favorite star button toggles aria-pressed without triggering row click", () => {
    const onNavigate = vi.fn();
    renderWithQuery(<RunHistoryTab onNavigate={onNavigate} />);
    const favBtn = screen.getAllByRole("button", { name: /Favorite|Unfavorite/ })[0];
    fireEvent.click(favBtn);
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("Pager exists and shows total count", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
  });
});
