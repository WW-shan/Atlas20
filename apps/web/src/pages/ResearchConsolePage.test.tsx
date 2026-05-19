import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { beforeEach, test, vi } from "vitest";

import * as api from "../lib/api";
import { qk } from "../lib/qk";
import { ResearchConsolePage } from "./ResearchConsolePage";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    getOverview: vi.fn(),
    getFeaturedDigest: vi.fn(),
    listReports: vi.fn(),
  };
});

const tabNames = ["Overview", "Backtest", "Compare", "History", "Universe", "Reports"];

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    client,
    ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getOverview).mockResolvedValue(api.fallbackOverview);
  vi.mocked(api.getFeaturedDigest).mockResolvedValue(api.fallbackFeaturedDigest);
  vi.mocked(api.listReports).mockResolvedValue(api.fallbackReports);
});

test("renders Atlas20 Research Console with 6 tabs", async () => {
  renderWithQuery(<ResearchConsolePage />);

  expect(screen.getByText("ATLAS20")).toBeInTheDocument();

  for (const name of tabNames) {
    expect(screen.getByRole("tab", { name })).toBeInTheDocument();
  }

  const overviewTab = screen.getByRole("tab", { name: "Overview" });
  expect(overviewTab).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByText("CURRENT CHAMPION")).toBeInTheDocument();
});

test("clicking tab switches content", async () => {
  renderWithQuery(<ResearchConsolePage />);

  const overviewTab = screen.getByRole("tab", { name: "Overview" });
  const reportsTab = screen.getByRole("tab", { name: "Reports" });

  act(() => { reportsTab.click(); });

  expect(reportsTab).toHaveAttribute("aria-selected", "true");
  expect(overviewTab).toHaveAttribute("aria-selected", "false");
  expect(await screen.findByText("FEATURED DIGEST")).toBeInTheDocument();
});

test("shows a page skeleton while the overview query is loading", () => {
  vi.mocked(api.getOverview).mockImplementation(() => new Promise<api.OverviewPayload>(() => {}));

  renderWithQuery(<ResearchConsolePage />);

  expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
});

test("shows an error banner when the overview query fails", async () => {
  vi.mocked(api.getOverview).mockRejectedValue(new Error("backend offline"));

  renderWithQuery(<ResearchConsolePage />);

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Unable to load overview");
});

test("keeps cached overview data visible and shows stale state when a refetch fails", async () => {
  vi.mocked(api.getOverview)
    .mockResolvedValueOnce(api.fallbackOverview)
    .mockRejectedValueOnce(new Error("backend offline"));

  const { client } = renderWithQuery(<ResearchConsolePage />);

  expect(await screen.findByText("CURRENT CHAMPION")).toBeInTheDocument();

  await act(async () => {
    await client.invalidateQueries({ queryKey: qk.overview() });
  });

  const staleIndicator = await screen.findByTestId("overview-stale-indicator");
  expect(staleIndicator).toBeInTheDocument();
  expect(staleIndicator).toHaveTextContent("stale — refresh failed");
  expect(screen.getByText("CURRENT CHAMPION")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
