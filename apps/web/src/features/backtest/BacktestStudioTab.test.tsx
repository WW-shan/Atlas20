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
    listRuns: vi.fn(),
    listRunsQueue: vi.fn(),
    runBacktest: vi.fn(),
    generateReport: vi.fn(),
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
  vi.mocked(api.listRuns).mockResolvedValue({
    items: api.fallbackRunsList,
    total: api.fallbackRunsList.length,
    page: 1,
    pageSize: 10,
  });
  vi.mocked(api.listRunsQueue).mockResolvedValue(api.fallbackRunsQueue);
  vi.mocked(api.runBacktest).mockResolvedValue(api.fallbackRunsQueue[0]);
  vi.mocked(api.generateReport).mockResolvedValue({
    job_id: "report-btk_0142",
    status: "completed",
    files: [],
    warnings: [],
  });
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

    renderWithQuery(<BacktestStudioTab prefillRunId="btk_0142" onNavigate={() => {}} />);
    const button = await screen.findByRole("button", { name: /RUN BACKTEST/ });
    expect(button).toBeInTheDocument();

    fireEvent.click(button);

    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("keeps a submitted run selected after it leaves the active queue", async () => {
    const historyRun = { ...api.fallbackRunsList[6], run_id: "btk_0100" };
    const submittedRun: api.RunRowSummary = {
      ...api.fallbackRunsQueue[0],
      run_id: "btk_0200",
      status: "queued",
      params_summary: "N=20 / Weekly / 2024-2026",
    };

    vi.mocked(api.listRunsQueue).mockResolvedValue([]);
    vi.mocked(api.listRuns).mockResolvedValue({
      items: [historyRun],
      total: 1,
      page: 1,
      pageSize: 10,
    });
    vi.mocked(api.runBacktest).mockResolvedValue(submittedRun);
    vi.mocked(api.getRunDetail).mockImplementation(async (runId: string) => ({
      ...api.fallbackRunDetail,
      run_id: runId,
      status: runId === submittedRun.run_id ? "queued" : "completed",
    }));

    const { client } = renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);

    expect(await screen.findByText(historyRun.run_id)).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: /RUN BACKTEST/ }));

    expect((await screen.findAllByText(submittedRun.run_id)).length).toBeGreaterThan(0);
    expect(await screen.findByText("Waiting for backend output")).toBeInTheDocument();

    act(() => {
      client.setQueryData(qk.runs.queue(), []);
    });

    await waitFor(() => expect(screen.getAllByText(submittedRun.run_id).length).toBeGreaterThan(0));
    expect(screen.queryByText(historyRun.run_id)).not.toBeInTheDocument();
  });

  it.each([
    [
      422,
      "validation_error",
      "unknown preset 'universe_refresh'",
      null,
      "Unable to queue backtest: unknown preset 'universe_refresh'",
    ],
    [
      409,
      "conflict",
      "a request with this Idempotency-Key is still in progress",
      null,
      "Unable to queue backtest: a request with this Idempotency-Key is still in progress",
    ],
    [
      429,
      "rate_limited",
      "Rate limit exceeded",
      { limit: "10 per 1 minute" },
      "Unable to queue backtest: Rate limit exceeded (10 per 1 minute)",
    ],
  ])("surfaces a %i RUN BACKTEST rejection with the backend message", async (status, code, message, details, expected) => {
    vi.mocked(api.runBacktest).mockRejectedValue(new api.ApiError(message, { status, code, details }));

    renderWithQuery(<BacktestStudioTab prefillRunId="btk_0142" onNavigate={() => {}} />);
    const button = await screen.findByRole("button", { name: /RUN BACKTEST/ });
    fireEvent.click(button);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(expected);
    await waitFor(() => expect(button).not.toBeDisabled());
  });

  it("re-runs a legacy non-Top-20 run on the point-in-time Top 20 universe", async () => {
    vi.mocked(api.getRunDetail).mockResolvedValue({ ...api.fallbackRunDetail, run_id: "btk_0141", universe: "Top-10" });

    renderWithQuery(<BacktestStudioTab prefillRunId="btk_0141" onNavigate={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /RUN BACKTEST/ }));

    await waitFor(() => expect(api.runBacktest).toHaveBeenCalled());
    expect(vi.mocked(api.runBacktest).mock.calls[0][0].universe.topN).toBe(20);
  });

  it("does not auto-select the daily universe_refresh job from the run queue", async () => {
    vi.mocked(api.listRunsQueue).mockResolvedValue([
      { run_id: "btk_0300", strategy: "universe_refresh", status: "running", duration_s: 5, params_summary: "Data Sources" },
    ]);

    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);

    await waitFor(() => expect(api.getRunDetail).toHaveBeenCalledWith("btk_0146"));
    expect(api.getRunDetail).not.toHaveBeenCalledWith("btk_0300");
  });

  it("falls back to the latest completed backtest even when refresh jobs fill the recent history", async () => {
    const refreshRow = (index: number): api.RunRow => ({
      run_id: `btk_04${String(index).padStart(2, "0")}`,
      strategy: "universe_refresh",
      strategy_family: "Other",
      universe: "Data Sources",
      window: { start: "2026-09-01", end: "2026-09-01" },
      status: index % 2 === 0 ? "completed" : "failed",
      created_at: `2026-09-${String(20 - index).padStart(2, "0")}T00:00:00Z`,
    });
    const backtest: api.RunRow = { ...api.fallbackRunsList[6], run_id: "btk_0142" };
    vi.mocked(api.listRunsQueue).mockResolvedValue([]);
    vi.mocked(api.listRuns).mockImplementation(async (filter) => {
      const rows = [...Array.from({ length: 12 }, (_, index) => refreshRow(index)), backtest]
        .filter((row) => filter.chips.length === 0 || filter.chips.includes(row.status));
      return { items: rows.slice(0, filter.pageSize), total: rows.length, page: 1, pageSize: filter.pageSize };
    });

    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);

    await waitFor(() => expect(api.getRunDetail).toHaveBeenCalledWith("btk_0142"));
  });

  it("does not let a queue poll that started before submission drop the new run", async () => {
    const submittedRun: api.RunRowSummary = {
      ...api.fallbackRunsQueue[0],
      run_id: "btk_0200",
      status: "queued",
      params_summary: "N=20 / Weekly / 2024-2026",
    };
    let resolveStalePoll: (runs: api.RunRowSummary[]) => void = () => {};
    vi.mocked(api.listRunsQueue)
      .mockImplementationOnce(() => new Promise<api.RunRowSummary[]>((resolve) => { resolveStalePoll = resolve; }))
      .mockResolvedValue([submittedRun]);
    vi.mocked(api.runBacktest).mockResolvedValue(submittedRun);

    renderWithQuery(<BacktestStudioTab prefillRunId="btk_0142" onNavigate={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /RUN BACKTEST/ }));
    expect(await screen.findByText("Backtest queued: btk_0200")).toBeInTheDocument();

    await act(async () => {
      resolveStalePoll([]);
    });

    const queuePanel = await screen.findByRole("complementary", { name: "Run queue" });
    await waitFor(() => expect(queuePanel).toHaveTextContent("btk_0200"));
    expect(screen.queryByText("Backtest completed: btk_0200")).not.toBeInTheDocument();
  });

  it("renders + NEW RUN button", async () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(await screen.findByRole("button", { name: /\+ NEW RUN/ })).toBeInTheDocument();
  });

  it("regenerates a report for the selected run", async () => {
    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    const button = await screen.findByRole("button", { name: "Regenerate this run's report" });
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    await waitFor(() => expect(api.generateReport).toHaveBeenCalledWith({
      type: "run",
      run_id: "btk_0142",
      formats: ["markdown", "pdf", "png", "bundle"],
    }));
  });

  it("reports a failed report regeneration as an error with the backend message", async () => {
    vi.mocked(api.generateReport).mockRejectedValue(new api.ApiError("run artifacts not found", { status: 404, code: "not_found" }));

    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    const button = await screen.findByRole("button", { name: "Regenerate this run's report" });
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to regenerate report: run artifacts not found");
    expect(screen.queryByText("Report regeneration failed")).not.toBeInTheDocument();
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

    renderWithQuery(<BacktestStudioTab prefillRunId="btk_0142" onNavigate={() => {}} />);

    expect(screen.getByTestId("backtest-detail-skeleton")).toBeInTheDocument();
    expect(screen.queryByLabelText("Backtest parameters")).not.toBeInTheDocument();
  });

  it("keeps the parameter sidebar visible with a refreshing badge during cached detail refetch", async () => {
    vi.mocked(api.getRunDetail)
      .mockResolvedValueOnce(api.fallbackRunDetail)
      .mockImplementationOnce(() => new Promise<api.RunDetailPayload>(() => {}));

    const { client } = renderWithQuery(<BacktestStudioTab prefillRunId="btk_0142" onNavigate={() => {}} />);

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

    renderWithQuery(<BacktestStudioTab prefillRunId="btk_0142" onNavigate={() => {}} />);

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

  it("renders queue error banner and retries the queue query", async () => {
    vi.mocked(api.listRunsQueue)
      .mockRejectedValueOnce(new Error("queue failed"))
      .mockResolvedValueOnce(api.fallbackRunsQueue);

    renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load run queue");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(api.listRunsQueue).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("RUN QUEUE")).toBeInTheDocument();
  });
});
