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
});
