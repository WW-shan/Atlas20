import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RunRow } from "../../lib/api";
import { RunTable } from "./RunTable";

function makeRow(status: RunRow["status"]): RunRow {
  return {
    run_id: "btk_cancelled",
    strategy: "ATLAS Adaptive v3",
    strategy_family: "ATLAS",
    universe: "Top-20",
    window: { start: "2024-01-01", end: "2026-05-18" },
    status,
    created_at: "2026-05-18T14:02:00Z",
  };
}

describe("RunTable", () => {
  it("renders a CANCELLED pill for cancelled runs", () => {
    render(
      <RunTable
        rows={[makeRow("cancelled" as RunRow["status"])]}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("CANCELLED")).toBeInTheDocument();
  });

  it("renders the selected strategy name and sparkline for history rows", () => {
    render(
      <RunTable
        rows={[
          {
            ...makeRow("completed" as RunRow["status"]),
            strategy: "base",
            selected_strategy: "Mean Reversion v2",
            return_pct: 0.21,
            spark: [0, 5, 10],
          } as RunRow,
        ]}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Mean Reversion v2")).toBeInTheDocument();
    expect(screen.getByLabelText("Trend for btk_cancelled")).toBeInTheDocument();
  });
});
