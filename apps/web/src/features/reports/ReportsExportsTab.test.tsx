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
    downloadDigest: vi.fn(),
    downloadReport: vi.fn(),
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
  vi.mocked(api.downloadDigest).mockResolvedValue({ url: "stub" });
  vi.mocked(api.downloadReport).mockResolvedValue({ url: "stub" });
  vi.mocked(api.getOptions).mockResolvedValue(api.fallbackOptions);
  vi.mocked(api.generateReport).mockResolvedValue({
    job_id: "stub-job-001",
    status: "queued",
    note: "report generation stubbed until Batch 12",
  });
});

describe("ReportsExportsTab", () => {
  it("renders FEATURED DIGEST hero label", async () => {
    renderWithQuery(<ReportsExportsTab />);
    expect(await screen.findByText("FEATURED DIGEST")).toBeInTheDocument();
  });

  it("renders 4 format buttons with markdown selected by default", async () => {
    renderWithQuery(<ReportsExportsTab />);
    const group = await screen.findByRole("group", { name: "Digest format" });
    const buttons = group.querySelectorAll("button");
    expect(buttons.length).toBe(4);
    const md = screen.getByRole("button", { name: "markdown" });
    expect(md.getAttribute("aria-pressed")).toBe("true");
  });

  it("clicking a format toggles aria-pressed", async () => {
    renderWithQuery(<ReportsExportsTab />);
    const pdf = await screen.findByRole("button", { name: "pdf" });
    fireEvent.click(pdf);
    expect(pdf.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "markdown" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("renders DOWNLOAD ALL bundle button", async () => {
    renderWithQuery(<ReportsExportsTab />);
    expect(await screen.findByRole("button", { name: /DOWNLOAD ALL/ })).toBeInTheDocument();
  });

  it("clicking DOWNLOAD ALL invokes downloadDigest('bundle') regardless of selected format", async () => {
    vi.mocked(api.downloadDigest).mockImplementationOnce(() => new Promise<Awaited<ReturnType<typeof api.downloadDigest>>>(() => {}));

    renderWithQuery(<ReportsExportsTab />);
    fireEvent.click(await screen.findByRole("button", { name: "pdf" }));
    fireEvent.click(screen.getByRole("button", { name: /DOWNLOAD ALL/ }));
    expect(api.downloadDigest).toHaveBeenCalledWith("bundle");
  });

  it("disables DOWNLOAD ALL while the bundle download is pending", async () => {
    vi.mocked(api.downloadDigest).mockImplementation(() => new Promise<Awaited<ReturnType<typeof api.downloadDigest>>>(() => {}));

    renderWithQuery(<ReportsExportsTab />);
    const button = await screen.findByRole("button", { name: /DOWNLOAD ALL/ });

    fireEvent.click(button);

    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("per-card DOWNLOAD honors the selected page-level format", async () => {
    vi.mocked(api.downloadReport).mockImplementationOnce(() => new Promise<Awaited<ReturnType<typeof api.downloadReport>>>(() => {}));

    renderWithQuery(<ReportsExportsTab />);
    fireEvent.click(await screen.findByRole("button", { name: "pdf" }));
    const firstCardDownload = document.querySelector('button[aria-label^="Download "]') as HTMLButtonElement;
    fireEvent.click(firstCardDownload);
    expect(api.downloadReport).toHaveBeenCalledWith(expect.any(String), "pdf");
  });

  it("disables report download buttons while a card download is pending", async () => {
    vi.mocked(api.downloadReport).mockImplementation(() => new Promise<Awaited<ReturnType<typeof api.downloadReport>>>(() => {}));

    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });

    const firstDownload = screen.getByRole("button", { name: /Download Atlas20/ });
    const secondDownload = screen.getByRole("button", { name: /Download ATLAS Adaptive v3/ });

    fireEvent.click(firstDownload);

    await waitFor(() => expect(firstDownload).toBeDisabled());
    expect(firstDownload).toHaveAttribute("aria-busy", "true");
    expect(secondDownload).toBeDisabled();

    fireEvent.click(secondDownload);
    expect(api.downloadReport).toHaveBeenCalledTimes(1);
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
      target: { value: "Momentum Top-10" },
    });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "pdf" }));
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Notes" }), {
      target: { value: "include drawdown notes" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Generate" }));

    await waitFor(() => expect(api.generateReport).toHaveBeenCalledWith({
      type: "run",
      formats: ["markdown", "pdf"],
      strategy: "Momentum Top-10",
      notes: "include drawdown notes",
    }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "New report" })).not.toBeInTheDocument());
  });

  it("shows queued toast after report submission", async () => {
    renderWithQuery(<ReportsExportsTab />);

    fireEvent.click(await screen.findByRole("button", { name: /\+ NEW REPORT/ }));
    const dialog = await screen.findByRole("dialog", { name: "New report" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Generate" }));

    expect(await screen.findByText("Report queued for generation")).toBeInTheDocument();
  });

  it("generating card disables its DOWNLOAD button", async () => {
    renderWithQuery(<ReportsExportsTab />);
    await screen.findByRole("list", { name: "Reports archive list" });
    const generatingCard = document.querySelector('[data-report-id="r5"]');
    expect(generatingCard).not.toBeNull();
    const dl = generatingCard?.querySelector('button[aria-label^="Download"]') as HTMLButtonElement | null;
    expect(dl?.hasAttribute("disabled")).toBe(true);
  });

  it("shows featured error banner and disables the digest download button", async () => {
    vi.mocked(api.getFeaturedDigest).mockRejectedValue(new Error("featured failed"));

    renderWithQuery(<ReportsExportsTab />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load featured digest");
    expect(screen.getByRole("button", { name: /DOWNLOAD ALL/ })).toBeDisabled();
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
});
