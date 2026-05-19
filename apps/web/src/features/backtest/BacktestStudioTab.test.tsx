import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { qk } from "../../lib/qk";
import { BacktestStudioTab } from "./BacktestStudioTab";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    getRunDetail: vi.fn(),
    listRunsQueue: vi.fn(),
    runBacktest: vi.fn(),
  };
});

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    client,
    ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getRunDetail).mockResolvedValue(api.fallbackRunDetail);
  vi.mocked(api.listRunsQueue).mockResolvedValue(api.fallbackRunsQueue);
  vi.mocked(api.runBacktest).mockResolvedValue(api.fallbackRunsQueue[0]);
});

describe("BacktestStudioTab", () => {
  it("renders 5 parameter section headers", async () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(await screen.findByText("STRATEGY")).toBeInTheDocument();
    for (const label of ["STRATEGY", "UNIVERSE", "WINDOW", "ALLOCATION", "COSTS"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders 6 KPI labels in equity workspace ribbon", async () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(await screen.findByText("CAGR")).toBeInTheDocument();
    for (const label of ["CAGR", "Sharpe", "Sortino", "Max DD", "Calmar", "Win Rate"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("renders RUN BACKTEST and disables it while the run mutation is pending", async () => {
    vi.mocked(api.runBacktest).mockImplementation(() => new Promise<api.RunRowSummary>(() => {}));

    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    const button = await screen.findByRole("button", { name: /RUN BACKTEST/ });
    expect(button).toBeInTheDocument();

    fireEvent.click(button);

    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("renders + NEW RUN button", async () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(await screen.findByRole("button", { name: /\+ NEW RUN/ })).toBeInTheDocument();
  });

  it("renders Run Queue header with active count", async () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(await screen.findByText("RUN QUEUE")).toBeInTheDocument();
  });

  it("View all link navigates to history", async () => {
    const onNavigate = vi.fn();
    renderWithQuery(<BacktestStudioTab onNavigate={onNavigate} />);
    fireEvent.click(await screen.findByRole("button", { name: /View all/ }));
    expect(onNavigate).toHaveBeenCalledWith("history");
  });

  it("renders RUNNING pill (cyan + pulse) for running queue items", async () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect((await screen.findAllByText("RUNNING")).length).toBeGreaterThan(0);
  });

  it("renders detail skeletons while the run detail query is loading", () => {
    vi.mocked(api.getRunDetail).mockImplementation(() => new Promise<api.RunDetailPayload>(() => {}));

    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);

    expect(screen.getByTestId("backtest-detail-skeleton")).toBeInTheDocument();
    expect(screen.queryByLabelText("Backtest parameters")).not.toBeInTheDocument();
  });

  it("keeps the parameter sidebar visible with a refreshing badge during cached detail refetch", async () => {
    vi.mocked(api.getRunDetail)
      .mockResolvedValueOnce(api.fallbackRunDetail)
      .mockImplementationOnce(() => new Promise<api.RunDetailPayload>(() => {}));

    const { client } = renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);

    expect(await screen.findByLabelText("Backtest parameters")).toBeInTheDocument();

    act(() => {
      void client.invalidateQueries({ queryKey: qk.runs.detail("btk_0142") });
    });

    await waitFor(() => expect(api.getRunDetail).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Backtest parameters")).toBeInTheDocument();
    expect(screen.getByTestId("parameter-sidebar-refreshing")).toHaveTextContent("REFRESHING");
  });

  it("renders detail error banner and retries the detail query", async () => {
    vi.mocked(api.getRunDetail)
      .mockRejectedValueOnce(new Error("detail failed"))
      .mockResolvedValueOnce(api.fallbackRunDetail);

    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Unable to load run detail");

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(api.getRunDetail).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("STRATEGY")).toBeInTheDocument();
  });

  it("renders queue skeletons while the queue query is loading", async () => {
    vi.mocked(api.listRunsQueue).mockImplementation(() => new Promise<api.RunRowSummary[]>(() => {}));

    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);

    expect(await screen.findByText("STRATEGY")).toBeInTheDocument();
    expect(screen.getByTestId("run-queue-skeleton")).toBeInTheDocument();
  });
});
