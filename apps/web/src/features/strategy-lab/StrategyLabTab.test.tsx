import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StrategyLabTab } from "./StrategyLabTab";
import * as api from "../../lib/api";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../../lib/api");
  return {
    ...actual,
    getOptions: vi.fn(),
    submitStrategyLabBatch: vi.fn(),
    getStrategyLabBatch: vi.fn(),
  };
});

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("StrategyLabTab", () => {
  beforeEach(() => {
    vi.mocked(api.getOptions).mockResolvedValue(api.fallbackOptions);
    vi.mocked(api.submitStrategyLabBatch).mockResolvedValue({ batch_id: "lab_test", runs: [], total: 2 });
    vi.mocked(api.getStrategyLabBatch).mockResolvedValue({
      batch_id: "lab_test",
      status_counts: { queued: 1, running: 0, completed: 1, failed: 0, cancelled: 0 },
      runs: [],
      results: [
        {
          run_id: "btk_9991",
          preset: "base",
          topN: 20,
          rebalance: "Monthly",
          status: "completed",
          return_pct: 0.2,
          sharpe: 1.5,
          max_dd: -0.12,
          calmar: 1.6,
        },
      ],
    });
  });

  it("renders matrix controls and run count preview", async () => {
    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    expect(await screen.findByRole("heading", { name: "Experiment matrix" })).toBeInTheDocument();
    expect(screen.getByText(/runs selected/i)).toBeInTheDocument();
  });

  it("submits the selected matrix", async () => {
    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    fireEvent.click(await screen.findByRole("button", { name: /Queue experiment/i }));

    await waitFor(() => expect(api.submitStrategyLabBatch).toHaveBeenCalled());
    expect(vi.mocked(api.submitStrategyLabBatch).mock.calls[0][0].baseConfig).toEqual(api.defaultBacktestConfig);
  });

  it("renders status counts and opens a completed run", async () => {
    const onNavigate = vi.fn();
    renderWithQuery(<StrategyLabTab onNavigate={onNavigate} />);

    fireEvent.click(await screen.findByRole("button", { name: /Queue experiment/i }));
    expect(await screen.findByText("lab_test")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /Open btk_9991/i }));

    expect(onNavigate).toHaveBeenCalledWith("backtest", "btk_9991");
  });
});
