import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SparklineChart } from "./SparklineChart";
import { OverlayLineChart } from "./OverlayLineChart";

describe("SparklineChart", () => {
  it("renders SVG with default tone", () => {
    render(<SparklineChart points={[1, 2, 3, 4]} />);
    expect(screen.getByRole("img", { name: "Sparkline" })).toBeInTheDocument();
  });

  it("accepts numeric array points", () => {
    const { container } = render(<SparklineChart points={[10, 20, 15, 30]} tone="cyan" />);
    expect(container.querySelector("path")).toBeTruthy();
  });

  it("renders dashed line for muted-dashed tone", () => {
    const { container } = render(<SparklineChart points={[1, 2, 3]} tone="muted-dashed" />);
    const path = container.querySelector("path");
    expect(path?.getAttribute("stroke-dasharray")).toBe("3 3");
  });
});

describe("OverlayLineChart", () => {
  const series = [
    { ts: "2025-01", values: { atlas: 100, btc: 100 } },
    { ts: "2025-06", values: { atlas: 400, btc: 150 } },
    { ts: "2025-12", values: { atlas: 1200, btc: 220 } },
  ];

  it("renders two-line overlay", () => {
    render(
      <OverlayLineChart
        series={series}
        lines={[
          { id: "atlas", label: "ATLAS", tone: "gold", glow: true },
          { id: "btc", label: "BTC", tone: "violet" },
        ]}
        range="YTD"
      />,
    );
    expect(screen.getByRole("img", { name: /Overlay chart, range YTD/ })).toBeInTheDocument();
  });

  it("renders annotations as vertical lines", () => {
    const { container } = render(
      <OverlayLineChart
        series={series}
        lines={[{ id: "atlas", label: "ATLAS", tone: "gold" }]}
        range="YTD"
        annotations={[{ ts: "2025-06", label: "PEAK", tone: "gold" }]}
      />,
    );
    expect(container.querySelector("text[fill='var(--gold)']")).toBeTruthy();
  });

  it("renders empty state when no series", () => {
    render(
      <OverlayLineChart
        series={[]}
        lines={[]}
        range="ALL"
        ariaLabel="Empty"
      />,
    );
    expect(screen.getByRole("img", { name: "Empty" })).toBeInTheDocument();
  });
});
