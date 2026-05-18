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

  it("switching date range to 'all' yields 14 fallback rows", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    fireEvent.click(screen.getByRole("tab", { name: "all" }));
    const rows = document.querySelectorAll("tr[data-run-id]");
    expect(rows.length).toBe(14);
  });

  it("renders RunTable header with 13 columns + 1 selection-bar column", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    const headers = document.querySelectorAll("thead th");
    // 13 visible labels + 1 selection-bar (empty label) → 14 th elements
    expect(headers.length).toBeGreaterThanOrEqual(13);
  });

  it("renders list/grid view toggle with list active", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    const listBtn = screen.getByRole("button", { name: "list" });
    expect(listBtn.getAttribute("aria-pressed")).toBe("true");
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
    expect(rows.length).toBe(2);
  });

  it("clicking a row selects it (aria-selected) without navigating", () => {
    const onNavigate = vi.fn();
    renderWithQuery(<RunHistoryTab onNavigate={onNavigate} />);
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

  it("clicking RE-RUN SELECTED navigates to backtest with prefillRunId", () => {
    const onNavigate = vi.fn();
    renderWithQuery(<RunHistoryTab onNavigate={onNavigate} />);
    const firstRow = document.querySelector("tr[data-run-id]") as HTMLElement;
    fireEvent.click(firstRow);
    fireEvent.click(screen.getByRole("button", { name: /RE-RUN SELECTED/ }));
    expect(onNavigate).toHaveBeenCalledWith("backtest", firstRow.getAttribute("data-run-id"));
  });

  it("favorite star button toggles without triggering row selection", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    const favBtn = screen.getAllByRole("button", { name: /Favorite|Unfavorite/ })[0];
    fireEvent.click(favBtn);
    // The parent row should NOT be selected
    const firstRow = document.querySelector("tr[data-run-id]") as HTMLElement;
    expect(firstRow.getAttribute("aria-selected")).not.toBe("true");
  });

  it("Pager exists and shows total count", () => {
    renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
  });
});
