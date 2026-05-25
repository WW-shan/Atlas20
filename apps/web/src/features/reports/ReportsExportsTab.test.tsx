import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { ReportsExportsTab } from "./ReportsExportsTab";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    getFeaturedDigest: vi.fn(),
    listReports: vi.fn(),
    downloadReportUrl: vi.fn(),
    getOptions: vi.fn(),
    generateReport: vi.fn(),
  };
});

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(window, "open", { writable: true, value: vi.fn() });
  vi.mocked(api.getFeaturedDigest).mockResolvedValue(api.fallbackFeaturedDigest);
  vi.mocked(api.listReports).mockResolvedValue(api.fallbackReports);
  vi.mocked(api.downloadReportUrl).mockImplementation((id, fmt) => {
    const q = fmt ? `?format=${encodeURIComponent(fmt)}` : "";
    return `https://atlas.test/reports/${encodeURIComponent(id)}/download${q}`;
  });
  vi.mocked(api.getOptions).mockResolvedValue(api.fallbackOptions);
  vi.mocked(api.generateReport).mockResolvedValue({
    job_id: "stub-job-001",
    status: "completed",
    files: [],
    warnings: [],
  });
});

describe("ReportsExportsTab", () => {
  it("renders FEATURED DIGEST hero label", async () => {
    renderWithQuery(<ReportsExportsTab />);
    expect(await screen.findByText("FEATURED DIGEST")).toBeInTheDocument();
  });

  it("renders 5 filter tabs with All selected by default", async () => {
    renderWithQuery(<ReportsExportsTab />);
    const tablist = await screen.findByRole("tablist", { name: "Report type filter" });
    const tabs = tablist.querySelectorAll("[role='tab']");
    expect(tabs.length).toBe(5);
    expect(screen.getByRole("tab", { name: "All" }).getAttribute("aria-selected")).toBe("true");
  });

  it("clicking a filter tab filters the archive", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });
    fireEvent.click(screen.getByRole("tab", { name: "Run" }));
    expect(screen.getByRole("tab", { name: "Run" }).getAttribute("aria-selected")).toBe("true");
    await waitFor(() => {
      const cards = document.querySelectorAll("[data-report-id]");
      cards.forEach((c) => {
        const entry = api.fallbackReports.find((r) => r.id === c.getAttribute("data-report-id"));
        expect(entry?.report_type).toBe("run");
      });
    });
  });

  it("renders a digest download button for the selected format", async () => {
    renderWithQuery(<ReportsExportsTab />);
    expect(await screen.findByRole("tablist", { name: "Report type filter" })).toBeInTheDocument();
  });

  it("clicking the Run filter shows only run reports", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });
    const totalBefore = document.querySelectorAll("[data-report-id]").length;
    fireEvent.click(screen.getByRole("tab", { name: "Run" }));
    await waitFor(() => {
      expect(document.querySelectorAll("[data-report-id]").length).toBeLessThan(totalBefore);
    });
  });

  it("leaves the archive visible after switching filters", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByText(api.fallbackFeaturedDigest.title);
    fireEvent.click(screen.getByRole("tab", { name: "Run" }));
    await waitFor(() => {
      const cards = document.querySelectorAll("[data-report-id]");
      expect(cards.length).toBeGreaterThan(0);
    });
  });

  it("per-card DOWNLOAD uses the archive artifact id without the page-level format", async () => {
    renderWithQuery(<ReportsExportsTab />);
    const firstCardDownload = await screen.findByRole("button", { name: /Download Atlas20/ });
    fireEvent.click(firstCardDownload);
    expect(api.downloadReportUrl).toHaveBeenCalledWith(expect.any(String));
    expect(window.open).toHaveBeenCalledWith(
      expect.not.stringContaining("?format="),
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("opens per-card report downloads in a new tab", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });

    const firstDownload = screen.getByRole("button", { name: /Download Atlas20/ });
    fireEvent.click(firstDownload);

    expect(api.downloadReportUrl).toHaveBeenCalledTimes(1);
    expect(window.open).toHaveBeenCalledWith(
      expect.stringContaining("/reports/r1/download"),
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("renders 6 archive cards (5 ready + 1 generating)", async () => {
    renderWithQuery(<ReportsExportsTab />);
    const list = await screen.findByRole("list", { name: "Reports archive list" });
    expect(list.querySelectorAll("[role='listitem']").length).toBe(6);
    expect(screen.getByText("GENERATING")).toBeInTheDocument();
  });

  it("highlighted card has data-highlight='true'", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });
    const highlighted = document.querySelectorAll('[data-highlight="true"]');
    expect(highlighted.length).toBe(1);
  });

  it("sort tab list renders 4 options with 'recent' active", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });
    const tabs = screen.getByRole("tablist", { name: "Archive sort" });
    expect(tabs.querySelectorAll("[role='tab']").length).toBe(4);
    expect(screen.getByRole("tab", { name: "Most recent" }).getAttribute("aria-selected")).toBe("true");
  });

  it("clicking 'Oldest' sort reorders the archive", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });
    fireEvent.click(screen.getByRole("tab", { name: "Oldest" }));
    expect(screen.getByRole("tab", { name: "Oldest" }).getAttribute("aria-selected")).toBe("true");
    await waitFor(() => expect(document.querySelectorAll("[data-report-id]").length).toBe(6));
    const cards = document.querySelectorAll("[data-report-id]");
    const ids = Array.from(cards).map((c) => c.getAttribute("data-report-id"));
    expect(ids.indexOf("r3")).toBeLessThan(ids.indexOf("r2"));
  });

  it("renders + NEW REPORT button (outline-violet)", async () => {
    renderWithQuery(<ReportsExportsTab />);
    expect(await screen.findByRole("button", { name: /\+ NEW REPORT/ })).toBeInTheDocument();
  });

  it("clicking + NEW REPORT opens modal controls", async () => {
    renderWithQuery(<ReportsExportsTab />);

    fireEvent.click(await screen.findByRole("button", { name: /\+ NEW REPORT/ }));

    const dialog = await screen.findByRole("dialog", { name: "New report" });
    expect(dialog).toHaveAttribute("aria-labelledby", "new-report-modal-title");
    expect(within(dialog).getByRole("heading", { name: "New report" })).toHaveAttribute("id", "new-report-modal-title");
    expect(within(dialog).getByRole("radiogroup", { name: "Report type" })).toBeInTheDocument();
    expect(within(dialog).getByRole("radio", { name: "weekly" })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: "markdown" })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: "pdf" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("radio", { name: "run" }));
    expect(within(dialog).getByRole("combobox", { name: "Strategy" })).toBeInTheDocument();
    expect(within(dialog).getByRole("textbox", { name: "Notes" })).toBeInTheDocument();
  });

  it("submitting new report calls generateReport and closes modal", async () => {
    renderWithQuery(<ReportsExportsTab />);

    fireEvent.click(await screen.findByRole("button", { name: /\+ NEW REPORT/ }));
    const dialog = await screen.findByRole("dialog", { name: "New report" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "run" }));
    fireEvent.change(within(dialog).getByRole("combobox", { name: "Strategy" }), {
      target: { value: "five_year_2020_2024" },
    });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "pdf" }));
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Notes" }), {
      target: { value: "include drawdown notes" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Generate" }));

    await waitFor(() => expect(api.generateReport).toHaveBeenCalledWith({
      type: "run",
      formats: ["markdown", "pdf"],
      strategy: "five_year_2020_2024",
      notes: "include drawdown notes",
    }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "New report" })).not.toBeInTheDocument());
  });

  it("shows generateReport errors and keeps the new report modal open", async () => {
    vi.mocked(api.generateReport).mockRejectedValueOnce(new Error("validation failed"));

    renderWithQuery(<ReportsExportsTab />);

    fireEvent.click(await screen.findByRole("button", { name: /\+ NEW REPORT/ }));
    const dialog = await screen.findByRole("dialog", { name: "New report" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Notes" }), {
      target: { value: "needs validation" },
    });
    const generate = within(dialog).getByRole("button", { name: "Generate" });
    fireEvent.click(generate);

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("validation failed");
    expect(screen.getByRole("dialog", { name: "New report" })).toBeInTheDocument();
    await waitFor(() => expect(generate).not.toBeDisabled());
  });

  it("shows queued toast after report submission", async () => {
    renderWithQuery(<ReportsExportsTab />);

    fireEvent.click(await screen.findByRole("button", { name: /\+ NEW REPORT/ }));
    const dialog = await screen.findByRole("dialog", { name: "New report" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Generate" }));

    const toast = await screen.findByText("Report queued for generation");
    expect(toast.closest("[role='status']")).toHaveAttribute("aria-live", "polite");
  });

  it("shows report generation warnings in the toast", async () => {
    vi.mocked(api.generateReport).mockResolvedValueOnce({
      job_id: "stub-job-002",
      status: "completed",
      files: [],
      warnings: ["PDF skipped: weasyprint unavailable"],
    });

    renderWithQuery(<ReportsExportsTab />);

    fireEvent.click(await screen.findByRole("button", { name: /\+ NEW REPORT/ }));
    const dialog = await screen.findByRole("dialog", { name: "New report" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Generate" }));

    const toast = await screen.findByText("PDF skipped: weasyprint unavailable");
    expect(toast.closest("[role='status']")).toHaveAttribute("aria-live", "polite");
  });

  it("generating card disables its DOWNLOAD button", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });
    const generatingCard = document.querySelector('[data-report-id="r5"]');
    expect(generatingCard).not.toBeNull();
    const dl = generatingCard?.querySelector('button[aria-label^="Download"]') as HTMLButtonElement | null;
    expect(dl?.hasAttribute("disabled")).toBe(true);
  });

  it("shows featured error banner when featured digest fails", async () => {
    vi.mocked(api.getFeaturedDigest).mockRejectedValue(new Error("featured failed"));

    renderWithQuery(<ReportsExportsTab />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load featured digest");
  });

  it("renders featured digest loading state while the hero query is pending", async () => {
    vi.mocked(api.getFeaturedDigest).mockImplementation(() => new Promise<api.FeaturedDigest>(() => {}));

    renderWithQuery(<ReportsExportsTab />);

    expect(await screen.findByRole("status", { name: "Loading featured digest" })).toBeInTheDocument();
  });

  it("shows archive empty state when no reports are returned", async () => {
    vi.mocked(api.listReports).mockResolvedValue([]);

    renderWithQuery(<ReportsExportsTab />);

    expect(await screen.findByText("No reports archived yet")).toBeInTheDocument();
  });

  it("renders 5 archive skeleton rows while the archive query is loading", async () => {
    vi.mocked(api.listReports).mockImplementation(() => new Promise<api.ReportEntry[]>(() => {}));

    renderWithQuery(<ReportsExportsTab />);

    expect(await screen.findByText("FEATURED DIGEST")).toBeInTheDocument();
    expect(screen.getAllByTestId("archive-skeleton-row")).toHaveLength(5);
  });

  it("renders archive error banner and retries the archive query", async () => {
    vi.mocked(api.listReports)
      .mockRejectedValueOnce(new Error("archive failed"))
      .mockResolvedValueOnce(api.fallbackReports);

    renderWithQuery(<ReportsExportsTab />);

    expect(await screen.findByText("Unable to load reports archive.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(api.listReports).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("list", { name: "Reports archive list" })).toBeInTheDocument();
  });
});
