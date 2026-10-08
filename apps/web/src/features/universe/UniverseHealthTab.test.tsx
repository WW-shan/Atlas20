import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { UniverseHealthTab } from "./UniverseHealthTab";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    getUniverseTimeline: vi.fn(),
    getDataSources: vi.fn(),
    getDataAlerts: vi.fn(),
    refreshUniverse: vi.fn(),
    getUniverseRefreshStatus: vi.fn(),
  };
});

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getUniverseTimeline).mockResolvedValue(api.fallbackUniverseTimeline);
  vi.mocked(api.getDataSources).mockResolvedValue(api.fallbackDataSources);
  vi.mocked(api.getDataAlerts).mockResolvedValue(api.fallbackDataAlerts);
  vi.mocked(api.refreshUniverse).mockResolvedValue({ run_id: "btk_9999", status: "queued" });
});

describe("UniverseHealthTab", () => {
  it("renders Universe Timeline svg with aria-label", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(screen.getByRole("img", { name: /Universe composition timeline/ })).toBeInTheDocument();
  });

  it("disables FORCE REFRESH while refreshUniverse is pending", async () => {
    vi.mocked(api.refreshUniverse).mockImplementation(() => new Promise<Awaited<ReturnType<typeof api.refreshUniverse>>>(() => {}));

    renderWithQuery(<UniverseHealthTab />);
    const button = screen.getByRole("button", { name: /FORCE REFRESH/ });
    expect(button).toBeInTheDocument();

    fireEvent.click(button);

    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("renders one tile per live research provider", () => {
    renderWithQuery(<UniverseHealthTab />);
    const list = screen.getByRole("list", { name: "Data sources" });
    const items = list.querySelectorAll("[role='listitem']");
    expect(items.length).toBe(api.fallbackDataSources.length);
    expect(items.length).toBe(2);
  });

  it("reports both research providers as healthy", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(document.querySelectorAll('[data-status="healthy"]').length).toBe(2);
    expect(document.querySelectorAll('[data-status="degraded"]').length).toBe(0);
    expect(document.querySelectorAll('[data-status="error"]').length).toBe(0);
  });

  it("renders 6 data alerts with 3 rose / 2 cyan / 1 emerald distribution", () => {
    renderWithQuery(<UniverseHealthTab />);
    const alerts = screen.getByRole("list", { name: "Data alerts list" });
    const items = alerts.querySelectorAll("[role='listitem']");
    expect(items.length).toBe(6);
    expect(document.querySelectorAll('[data-alert-id][data-severity="rose"]').length).toBe(3);
    expect(document.querySelectorAll('[data-alert-id][data-severity="cyan"]').length).toBe(2);
    expect(document.querySelectorAll('[data-alert-id][data-severity="emerald"]').length).toBe(1);
  });

  it("DATA ALERTS section badge shows '5 OPEN' (resolved/emerald excluded)", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(screen.getByText("5 OPEN")).toBeInTheDocument();
  });

  it("uses three icon kinds: alert-triangle, info, check-circle", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(document.querySelectorAll('[data-icon="alert-triangle"]').length).toBeGreaterThanOrEqual(1);
    expect(document.querySelectorAll('[data-icon="info"]').length).toBeGreaterThanOrEqual(1);
    expect(document.querySelectorAll('[data-icon="check-circle"]').length).toBeGreaterThanOrEqual(1);
  });

  it("does NOT use a lucide 'InfoCircle' name (verify info kind only)", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(document.querySelectorAll('[data-icon="InfoCircle"]').length).toBe(0);
    expect(document.querySelectorAll('[data-icon="info-circle"]').length).toBe(0);
  });

  it("surfaces a rate-limited FORCE REFRESH (429) with the backend message", async () => {
    vi.mocked(api.refreshUniverse).mockRejectedValueOnce(
      new api.ApiError("Rate limit exceeded", { status: 429, code: "rate_limited", details: { limit: "1 per 1 minute" } }),
    );

    renderWithQuery(<UniverseHealthTab />);
    fireEvent.click(screen.getByRole("button", { name: /FORCE REFRESH/ }));

    const message = await screen.findByText("Unable to refresh universe data: Rate limit exceeded (1 per 1 minute)");
    expect(message.closest("[role='alert']")).not.toBeNull();
  });

  it("labels a data source that has never synced instead of inventing an age", async () => {
    vi.mocked(api.getDataSources).mockResolvedValue([
      { id: "gate", name: "Gate · Price cross-check", status: "error", last_sync_seconds: 999_999 },
    ]);

    renderWithQuery(<UniverseHealthTab apiEnabled />);

    expect(await screen.findByText("Last sync · never")).toBeInTheDocument();
    expect(screen.queryByText(/11d ago/)).not.toBeInTheDocument();
  });

  it("reloads universe data once the queued FORCE REFRESH job completes, then stops polling", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      vi.mocked(api.refreshUniverse).mockResolvedValue({ run_id: "btk_0500", status: "queued" });
      vi.mocked(api.getUniverseRefreshStatus)
        .mockResolvedValueOnce({ run_id: "btk_0500", status: "running" })
        .mockResolvedValue({ run_id: "btk_0500", status: "completed" });

      renderWithQuery(<UniverseHealthTab apiEnabled />);
      fireEvent.click(await screen.findByRole("button", { name: /FORCE REFRESH/ }));

      expect(await screen.findByText(/Refresh btk_0500 running/)).toBeInTheDocument();
      expect(api.getDataSources).toHaveBeenCalledTimes(1);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });

      expect(await screen.findByText("Universe data refreshed (btk_0500)")).toBeInTheDocument();
      await waitFor(() => expect(api.getDataSources).toHaveBeenCalledTimes(2));
      const statusCalls = vi.mocked(api.getUniverseRefreshStatus).mock.calls.length;

      await act(async () => {
        await vi.advanceTimersByTimeAsync(15_000);
      });
      expect(api.getUniverseRefreshStatus).toHaveBeenCalledTimes(statusCalls);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps universe data visible after a refresh failure", async () => {
    vi.mocked(api.refreshUniverse).mockRejectedValueOnce(new Error("refresh failed"));

    renderWithQuery(<UniverseHealthTab />);
    const button = screen.getByRole("button", { name: /FORCE REFRESH/ });
    fireEvent.click(button);

    await waitFor(() => expect(api.refreshUniverse).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(button).not.toBeDisabled());
    expect(screen.getByRole("list", { name: "Data sources" }).querySelectorAll("[role='listitem']")).toHaveLength(2);
  });

  it("renders tab-level skeletons while universe queries are loading", () => {
    vi.mocked(api.getUniverseTimeline).mockImplementation(() => new Promise<api.UniverseTimelinePayload>(() => {}));
    vi.mocked(api.getDataSources).mockImplementation(() => new Promise<api.DataSource[]>(() => {}));
    vi.mocked(api.getDataAlerts).mockImplementation(() => new Promise<api.DataAlert[]>(() => {}));

    renderWithQuery(<UniverseHealthTab apiEnabled />);

    expect(screen.getAllByTestId("universe-skeleton")).toHaveLength(3);
  });

  it("renders tab-level error banner and retries universe queries", async () => {
    vi.mocked(api.getUniverseTimeline)
      .mockRejectedValueOnce(new Error("timeline failed"))
      .mockResolvedValueOnce(api.fallbackUniverseTimeline);
    vi.mocked(api.getDataSources)
      .mockRejectedValueOnce(new Error("sources failed"))
      .mockResolvedValueOnce(api.fallbackDataSources);
    vi.mocked(api.getDataAlerts)
      .mockRejectedValueOnce(new Error("alerts failed"))
      .mockResolvedValueOnce(api.fallbackDataAlerts);

    renderWithQuery(<UniverseHealthTab apiEnabled />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load universe data");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(api.getUniverseTimeline).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("img", { name: /Universe composition timeline/ })).toBeInTheDocument();
  });

  it("renders tab-level empty state when timeline and sources are empty", async () => {
    vi.mocked(api.getUniverseTimeline).mockResolvedValue({
      tokens: [],
      segments: [],
      rotations: [],
      range: { start: "2026-01-01", end: "2026-01-02" },
      data_source: "fallback",
    });
    vi.mocked(api.getDataSources).mockResolvedValue([]);
    vi.mocked(api.getDataAlerts).mockResolvedValue([]);

    renderWithQuery(<UniverseHealthTab apiEnabled />);

    expect(await screen.findByText("No universe data available")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /Universe composition timeline/ })).not.toBeInTheDocument();
  });
});
