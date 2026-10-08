import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

  it("loads presets from /api/options instead of pinning the static fallback list", async () => {
    vi.mocked(api.getOptions).mockResolvedValue({
      ...api.fallbackOptions,
      presets: [
        { slug: "base", display_name: "Base Config" },
        { slug: "phase_momentum", display_name: "Phase Momentum" },
      ],
    });

    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    expect(await screen.findByRole("checkbox", { name: "Phase Momentum" })).toBeInTheDocument();
    expect(api.getOptions).toHaveBeenCalled();
    expect(screen.queryByRole("checkbox", { name: "Five Year 2020 2024" })).not.toBeInTheDocument();
  });

  it("keeps the default preset visible when /api/options does not list it", async () => {
    vi.mocked(api.getOptions).mockResolvedValue({
      ...api.fallbackOptions,
      presets: [{ slug: "TOP20_MOM_top6_monthly__always_on", display_name: "Momentum Rotation · Top6 Monthly" }],
    });

    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    expect(await screen.findByRole("checkbox", { name: "Momentum Rotation · Top6 Monthly" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "base" })).toBeChecked();
    expect(screen.getByText("1 runs selected")).toBeInTheDocument();
  });

  it("surfaces an /api/options failure and blocks queuing placeholder presets", async () => {
    vi.mocked(api.getOptions).mockRejectedValue(new api.ApiError("Internal server error", { status: 500 }));

    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load Strategy Lab presets: Internal server error");
    expect(screen.getByRole("button", { name: /Queue experiment/i })).toBeDisabled();
  });

  it("submits the selected matrix", async () => {
    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    fireEvent.click(await screen.findByRole("button", { name: /Queue experiment/i }));

    await waitFor(() => expect(api.submitStrategyLabBatch).toHaveBeenCalled());
    expect(vi.mocked(api.submitStrategyLabBatch).mock.calls[0][0].baseConfig).toEqual(api.defaultBacktestConfig);
  });

  it("surfaces a rate-limited (429) batch submission with the backend message", async () => {
    vi.mocked(api.submitStrategyLabBatch).mockRejectedValue(
      new api.ApiError("Rate limit exceeded", { status: 429, code: "rate_limited", details: { limit: "1 per 1 minute" } }),
    );
    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    fireEvent.click(await screen.findByRole("button", { name: /Queue experiment/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to queue Strategy Lab experiment: Rate limit exceeded (1 per 1 minute)",
    );
  });

  it("queues only point-in-time Top 20 universes", async () => {
    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    fireEvent.click(await screen.findByRole("button", { name: /Queue experiment/i }));

    await waitFor(() => expect(api.submitStrategyLabBatch).toHaveBeenCalled());
    expect(vi.mocked(api.submitStrategyLabBatch).mock.calls.at(-1)?.[0].topNs).toEqual([20]);
    expect(screen.queryByRole("checkbox", { name: "Top 10" })).not.toBeInTheDocument();
  });

  it("labels return_pct as total return rather than CAGR", async () => {
    renderWithQuery(<StrategyLabTab onNavigate={() => {}} />);

    fireEvent.click(await screen.findByRole("button", { name: /Queue experiment/i }));
    const table = await screen.findByRole("table");

    expect(within(table).getByRole("columnheader", { name: "Total Return" })).toBeInTheDocument();
    expect(within(table).queryByRole("columnheader", { name: "CAGR" })).not.toBeInTheDocument();
    expect(within(table).getByRole("cell", { name: "20.0%" })).toBeInTheDocument();
    const sort = screen.getByRole("combobox", { name: "Sort Strategy Lab results" });
    expect(within(sort).getByRole("option", { name: "Total Return" })).toBeInTheDocument();
    expect(within(sort).queryByRole("option", { name: "CAGR" })).not.toBeInTheDocument();
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
