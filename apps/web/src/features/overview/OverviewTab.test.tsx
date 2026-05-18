import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OverviewTab } from "./OverviewTab";
import { fallbackOverview } from "../../lib/api";

describe("OverviewTab", () => {
  it("renders hero with CURRENT CHAMPION + ATLAS title", () => {
    render(<OverviewTab overview={fallbackOverview} onNavigate={() => {}} />);
    expect(screen.getByText("CURRENT CHAMPION")).toBeInTheDocument();
    // ATLAS Adaptive v3 appears in both hero <h2> and equity overlay legend
    expect(screen.getAllByText("ATLAS Adaptive v3").length).toBeGreaterThanOrEqual(1);
  });

  it("renders 4 hero KPIs", () => {
    render(<OverviewTab overview={fallbackOverview} onNavigate={() => {}} />);
    expect(screen.getByRole("group", { name: "YTD Return" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Sharpe" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Max DD" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Win Rate" })).toBeInTheDocument();
  });

  it("renders 3 KPI section labels", () => {
    render(<OverviewTab overview={fallbackOverview} onNavigate={() => {}} />);
    expect(screen.getByText("TOTAL AUM TRACKED")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE STRATEGIES")).toBeInTheDocument();
    expect(screen.getByText("MARKET REGIME")).toBeInTheDocument();
  });

  it("renders 4 rebalance swap rows with OUT/IN labels", () => {
    const { container } = render(<OverviewTab overview={fallbackOverview} onNavigate={() => {}} />);
    const outCount = Array.from(container.querySelectorAll("span")).filter((el) => el.textContent === "OUT").length;
    const inCount = Array.from(container.querySelectorAll("span")).filter((el) => el.textContent === "IN").length;
    expect(outCount).toBe(4);
    expect(inCount).toBe(4);
  });

  it("equity overlay renders with two lines (gold ATLAS + violet BTC)", () => {
    render(<OverviewTab overview={fallbackOverview} onNavigate={() => {}} />);
    expect(screen.getByRole("img", { name: /ATLAS vs BTC equity curve/ })).toBeInTheDocument();
  });

  it("RegimeGauge has role=meter", () => {
    render(<OverviewTab overview={fallbackOverview} onNavigate={() => {}} />);
    expect(screen.getByRole("meter")).toBeInTheDocument();
  });

  it("clicking GENERATE REPORT navigates to reports", () => {
    const onNavigate = vi.fn();
    render(<OverviewTab overview={fallbackOverview} onNavigate={onNavigate} />);
    screen.getByRole("button", { name: /GENERATE REPORT/i }).click();
    expect(onNavigate).toHaveBeenCalledWith("reports");
  });

  it("clicking RUN NEW BACKTEST navigates to backtest tab", () => {
    const onNavigate = vi.fn();
    render(<OverviewTab overview={fallbackOverview} onNavigate={onNavigate} />);
    screen.getByRole("button", { name: /RUN NEW BACKTEST/i }).click();
    expect(onNavigate).toHaveBeenCalledWith("backtest");
  });

  it("clicking COMPARE STRATEGIES navigates to compare", () => {
    const onNavigate = vi.fn();
    render(<OverviewTab overview={fallbackOverview} onNavigate={onNavigate} />);
    screen.getByRole("button", { name: /COMPARE STRATEGIES/i }).click();
    expect(onNavigate).toHaveBeenCalledWith("compare");
  });

  it("RISK-ON label visible in regime gauge", () => {
    render(<OverviewTab overview={fallbackOverview} onNavigate={() => {}} />);
    expect(screen.getByText("RISK-ON")).toBeInTheDocument();
  });
});
