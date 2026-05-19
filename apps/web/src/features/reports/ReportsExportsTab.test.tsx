import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    renderWithQuery(<ReportsExportsTab />);
    fireEvent.click(await screen.findByRole("button", { name: "pdf" }));
    fireEvent.click(screen.getByRole("button", { name: /DOWNLOAD ALL/ }));
    expect(api.downloadDigest).toHaveBeenCalledWith("bundle");
  });

  it("per-card DOWNLOAD honors the selected page-level format", async () => {
    renderWithQuery(<ReportsExportsTab />);
    fireEvent.click(await screen.findByRole("button", { name: "pdf" }));
    const firstCardDownload = document.querySelector('button[aria-label^="Download "]') as HTMLButtonElement;
    fireEvent.click(firstCardDownload);
    expect(api.downloadReport).toHaveBeenCalledWith(expect.any(String), "pdf");
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
