import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BacktestStudioTab } from "./BacktestStudioTab";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("BacktestStudioTab", () => {
  it("renders 5 parameter section headers", () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    for (const label of ["STRATEGY", "UNIVERSE", "WINDOW", "ALLOCATION", "COSTS"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders 6 KPI labels in equity workspace ribbon", () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    for (const label of ["CAGR", "Sharpe", "Sortino", "Max DD", "Calmar", "Win Rate"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("renders RUN BACKTEST gold button", () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(screen.getByRole("button", { name: /RUN BACKTEST/ })).toBeInTheDocument();
  });

  it("renders + NEW RUN button", () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(screen.getByRole("button", { name: /\+ NEW RUN/ })).toBeInTheDocument();
  });

  it("renders Run Queue header with active count", () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(screen.getByText("RUN QUEUE")).toBeInTheDocument();
  });

  it("View all link navigates to history", () => {
    const onNavigate = vi.fn();
    renderWithQuery(<BacktestStudioTab onNavigate={onNavigate} />);
    screen.getByRole("button", { name: /View all/ }).click();
    expect(onNavigate).toHaveBeenCalledWith("history");
  });

  it("renders RUNNING pill (cyan + pulse) for running queue items", () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(screen.getAllByText("RUNNING").length).toBeGreaterThan(0);
  });
});
