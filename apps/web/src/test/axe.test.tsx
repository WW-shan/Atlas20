import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { OverviewTab } from "../features/overview/OverviewTab";
import { BacktestStudioTab } from "../features/backtest/BacktestStudioTab";
import { StrategyCompareTab } from "../features/compare/StrategyCompareTab";
import { RunHistoryTab } from "../features/history/RunHistoryTab";
import { UniverseHealthTab } from "../features/universe/UniverseHealthTab";
import { ReportsExportsTab } from "../features/reports/ReportsExportsTab";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    getRunDetail: vi.fn(),
    listRunsQueue: vi.fn(),
    listRuns: vi.fn(),
    toggleFavorite: vi.fn(),
    getCompare: vi.fn(),
    getOptions: vi.fn(),
    getFeaturedDigest: vi.fn(),
    listReports: vi.fn(),
    generateReport: vi.fn(),
  };
});

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const axeOptions = {
  rules: {
    "color-contrast": { enabled: false },
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getRunDetail).mockResolvedValue(api.fallbackRunDetail);
  vi.mocked(api.listRunsQueue).mockResolvedValue(api.fallbackRunsQueue);
  vi.mocked(api.listRuns).mockResolvedValue({
    items: api.fallbackRunsList.slice(0, 14),
    total: api.fallbackRunsList.length,
    page: 1,
    pageSize: 14,
  });
  vi.mocked(api.toggleFavorite).mockResolvedValue({ run_id: "btk_0142", favorited: false });
  vi.mocked(api.getCompare).mockResolvedValue(api.fallbackCompare);
  vi.mocked(api.getOptions).mockResolvedValue(api.fallbackOptions);
  vi.mocked(api.getFeaturedDigest).mockResolvedValue(api.fallbackFeaturedDigest);
  vi.mocked(api.listReports).mockResolvedValue(api.fallbackReports);
  vi.mocked(api.generateReport).mockResolvedValue({
    job_id: "stub-job-001",
    status: "completed",
    note: "stub",
  });
});

describe("axe accessibility", () => {
  it("OverviewTab has no axe violations", async () => {
    const { container } = render(<OverviewTab overview={api.fallbackOverview} onNavigate={() => {}} />);
    expect(await axe(container, axeOptions)).toHaveNoViolations();
  });

  it("BacktestStudioTab has no axe violations", async () => {
    const { container } = renderWithQuery(<BacktestStudioTab onNavigate={() => {}} />);
    expect(await axe(container, axeOptions)).toHaveNoViolations();
  });

  it("StrategyCompareTab has no axe violations", async () => {
    const { container } = renderWithQuery(<StrategyCompareTab />);
    expect(await axe(container, axeOptions)).toHaveNoViolations();
  });

  it("RunHistoryTab has no axe violations", async () => {
    const { container } = renderWithQuery(<RunHistoryTab onNavigate={() => {}} />);
    expect(await axe(container, axeOptions)).toHaveNoViolations();
  });

  it("UniverseHealthTab has no axe violations", async () => {
    const { container } = renderWithQuery(<UniverseHealthTab />);
    expect(await axe(container, axeOptions)).toHaveNoViolations();
  });

  it("ReportsExportsTab has no axe violations", async () => {
    const { container } = renderWithQuery(<ReportsExportsTab />);
    expect(await axe(container, axeOptions)).toHaveNoViolations();
  });
});
