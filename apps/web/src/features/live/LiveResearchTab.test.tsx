import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { LiveResearchTab } from "./LiveResearchTab";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    getLiveResearch: vi.fn(),
  };
});

function renderWithQuery() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><LiveResearchTab /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getLiveResearch).mockResolvedValue(api.fallbackLiveResearch);
});

describe("LiveResearchTab", () => {
  it("renders the current spot research and OOS state", async () => {
    renderWithQuery();

    const spot = await screen.findByRole("region", { name: "Spot research" });
    expect(spot).toHaveTextContent("PR2026-10-H5");
    expect(spot).toHaveTextContent("provisional");
    expect(spot).toHaveTextContent("2026-10-08");
    expect(spot).toHaveTextContent("NEAR");
    expect(spot).toHaveTextContent("Target gross");
    expect(spot).toHaveTextContent("62.1%");

    const oos = screen.getByRole("region", { name: "Out-of-sample tracking" });
    expect(oos).toHaveTextContent("17 days");
    expect(oos).toHaveTextContent("H5");
    expect(oos).toHaveTextContent("96.8%");
    expect(oos).toHaveTextContent("BTC");
    expect(oos).toHaveTextContent("94.3%");
    expect(oos).toHaveTextContent("Short-window tracking; not a validation claim");
  });

  it("renders repeated frozen fill variants without duplicate React keys", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const first = api.fallbackLiveResearch.spot?.frozen?.[0];
    expect(first).toBeDefined();
    if (!first) throw new Error("fallback frozen metrics missing");
    vi.mocked(api.getLiveResearch).mockResolvedValue({
      ...api.fallbackLiveResearch,
      spot: {
        ...api.fallbackLiveResearch.spot!,
        frozen: [
          first,
          { ...first, trial_id: "PR2026-10-H5-T60", multiple: 16.0 },
        ],
      },
    });

    try {
      renderWithQuery();
      const spot = await screen.findByRole("region", { name: "Spot research" });
      expect(spot).toHaveTextContent("PR2026-10-H5");
      const duplicateKeyErrors = consoleError.mock.calls.filter((call) =>
        call.some((argument) => String(argument).includes("same key")),
      );
      expect(duplicateKeyErrors).toEqual([]);
    } finally {
      consoleError.mockRestore();
    }
  });

  it("renders derivatives health, equivalence, and journal rows", async () => {
    renderWithQuery();

    const derivatives = await screen.findByRole("region", { name: "Derivatives live monitor" });
    expect(derivatives).toHaveTextContent("healthy");
    expect(derivatives).toHaveTextContent("99.95 USDT equity");
    expect(derivatives).toHaveTextContent("75.11 USDT gross notional");
    expect(derivatives).toHaveTextContent("0 hard failures");
    expect(derivatives).toHaveTextContent("Signal equivalence passed");

    const journal = screen.getByRole("region", { name: "Execution journal" });
    expect(journal).toHaveTextContent("2026-10-10");
    expect(journal).toHaveTextContent("99.974147");
    expect(journal).toHaveTextContent("1 positions");
    expect(journal).toHaveTextContent("0 trades");
  });

  it("refreshes live research data", async () => {
    renderWithQuery();
    expect(await screen.findByRole("region", { name: "Spot research" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /REFRESH LIVE DATA/i }));

    await waitFor(() => expect(api.getLiveResearch).toHaveBeenCalledTimes(2));
  });

  it("reports unavailable artifacts without inventing data", async () => {
    vi.mocked(api.getLiveResearch).mockResolvedValue({
      spot: null,
      oos: null,
      derivatives: null,
      artifacts: [{ id: "spot_signal", section: "spot", path: "missing.json", available: false }],
    });

    renderWithQuery();

    expect(await screen.findByText("Live research artifacts unavailable")).toBeInTheDocument();
    expect(screen.getByText("spot_signal · missing.json · unavailable")).toBeInTheDocument();
  });

  it("shows and retries a live research error", async () => {
    vi.mocked(api.getLiveResearch)
      .mockRejectedValueOnce(new Error("live data failed"))
      .mockResolvedValueOnce(api.fallbackLiveResearch);

    renderWithQuery();

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load live research.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(api.getLiveResearch).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("region", { name: "Spot research" })).toBeInTheDocument();
  });
});
