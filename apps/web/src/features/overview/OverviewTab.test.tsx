import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OverviewTab } from "./OverviewTab";
import { fallbackOverview, type OverviewPayload } from "../../lib/api";

function withOverview(patch: Partial<OverviewPayload>): OverviewPayload {
  return { ...fallbackOverview, ...patch };
}

describe("OverviewTab", () => {
  it("renders hero with CURRENT CHAMPION + fallback atlas label", () => {
    render(<OverviewTab overview={fallbackOverview} onNavigate={() => {}} />);
    expect(screen.getByText("CURRENT CHAMPION")).toBeInTheDocument();
    expect(screen.getAllByText(fallbackOverview.equity_overlay.atlas_label).length).toBeGreaterThanOrEqual(1);
  });

  it("renders champion display name in hero", () => {
    const overview = withOverview({
      champion: {
        ...fallbackOverview.champion,
        strategy: "TOP20_MOM_top8_biweekly__bull_only",
        display_name: "Momentum Rotation · Top8 Biweekly",
      },
    });

    render(<OverviewTab overview={overview} onNavigate={() => {}} />);

    expect(screen.getByRole("heading", { name: "Momentum Rotation · Top8 Biweekly" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "TOP20_MOM_top8_biweekly__bull_only" })).not.toBeInTheDocument();
  });

  it("renders equity overlay atlas label in chart legend", () => {
    const overview = withOverview({
      equity_overlay: {
        ...fallbackOverview.equity_overlay,
        atlas_label: "Payload Atlas Label",
        btc_label: "Payload BTC Label",
      },
    });

    render(<OverviewTab overview={overview} onNavigate={() => {}} />);

    expect(screen.getByText("Payload Atlas Label")).toBeInTheDocument();
    expect(screen.getByText("Payload BTC Label")).toBeInTheDocument();
    expect(screen.queryByText("ATLAS Adaptive v3")).not.toBeInTheDocument();
  });

  it("renders rebalance cadence from champion payload", () => {
    const overview = withOverview({
      champion: { ...fallbackOverview.champion, rebalance_frequency: "Monthly" },
    });

    render(<OverviewTab overview={overview} onNavigate={() => {}} />);

    expect(screen.getByText(/Monthly/)).toBeInTheDocument();
    expect(screen.queryByText(/weekly/)).not.toBeInTheDocument();
  });

  it("formats last sync age from payload seconds", () => {
    const { rerender } = render(<OverviewTab overview={withOverview({ last_sync_seconds: 59 })} onNavigate={() => {}} />);
    expect(screen.getByText("59s ago")).toBeInTheDocument();

    rerender(<OverviewTab overview={withOverview({ last_sync_seconds: 60 })} onNavigate={() => {}} />);
    expect(screen.getByText("1m ago")).toBeInTheDocument();

    rerender(<OverviewTab overview={withOverview({ last_sync_seconds: 3599 })} onNavigate={() => {}} />);
    expect(screen.getByText("59m ago")).toBeInTheDocument();

    rerender(<OverviewTab overview={withOverview({ last_sync_seconds: 3600 })} onNavigate={() => {}} />);
    expect(screen.getByText("1h ago")).toBeInTheDocument();
  });

  it("renders equity chart empty-state copy", () => {
    const overview = withOverview({
      equity_overlay: { ...fallbackOverview.equity_overlay, series: [] },
    });

    render(<OverviewTab overview={overview} onNavigate={() => {}} />);

    expect(screen.getByText("No data in selected range")).toBeInTheDocument();
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
    expect(screen.getByText("TRACKED NOTIONAL · RESEARCH")).toBeInTheDocument();
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
