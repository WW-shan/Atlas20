import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { ReportsExportsTab } from "./ReportsExportsTab";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("ReportsExportsTab", () => {
  it("renders FEATURED DIGEST hero label", () => {
    renderWithQuery(<ReportsExportsTab />);
    expect(screen.getByText("FEATURED DIGEST")).toBeInTheDocument();
  });

  it("renders 4 format buttons with markdown selected by default", () => {
    renderWithQuery(<ReportsExportsTab />);
    const group = screen.getByRole("group", { name: "Digest format" });
    const buttons = group.querySelectorAll("button");
    expect(buttons.length).toBe(4);
    const md = screen.getByRole("button", { name: "markdown" });
    expect(md.getAttribute("aria-pressed")).toBe("true");
  });

  it("clicking a format toggles aria-pressed", () => {
    renderWithQuery(<ReportsExportsTab />);
    const pdf = screen.getByRole("button", { name: "pdf" });
    fireEvent.click(pdf);
    expect(pdf.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "markdown" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("renders DOWNLOAD ALL bundle button", () => {
    renderWithQuery(<ReportsExportsTab />);
    expect(screen.getByRole("button", { name: /DOWNLOAD ALL/ })).toBeInTheDocument();
  });

  it("clicking DOWNLOAD ALL invokes downloadDigest('bundle') regardless of selected format", () => {
    const spy = vi.spyOn(api, "downloadDigest").mockResolvedValue({ url: "stub" } as never);
    renderWithQuery(<ReportsExportsTab />);
    // Pick PDF first so we know format state is something other than 'bundle'
    fireEvent.click(screen.getByRole("button", { name: "pdf" }));
    fireEvent.click(screen.getByRole("button", { name: /DOWNLOAD ALL/ }));
    expect(spy).toHaveBeenCalledWith("bundle");
    spy.mockRestore();
  });

  it("per-card DOWNLOAD ↓ honors the selected page-level format", () => {
    const spy = vi.spyOn(api, "downloadReport").mockResolvedValue({ url: "stub" } as never);
    renderWithQuery(<ReportsExportsTab />);
    fireEvent.click(screen.getByRole("button", { name: "pdf" }));
    const firstCardDownload = document.querySelector('button[aria-label^="Download "]') as HTMLButtonElement;
    fireEvent.click(firstCardDownload);
    expect(spy).toHaveBeenCalledWith(expect.any(String), "pdf");
    spy.mockRestore();
  });

  it("renders 6 archive cards (5 ready + 1 generating)", () => {
    renderWithQuery(<ReportsExportsTab />);
    const list = screen.getByRole("list", { name: "Reports archive list" });
    expect(list.querySelectorAll("[role='listitem']").length).toBe(6);
    expect(screen.getByText("GENERATING")).toBeInTheDocument();
  });

  it("highlighted card has data-highlight='true'", () => {
    renderWithQuery(<ReportsExportsTab />);
    const highlighted = document.querySelectorAll('[data-highlight="true"]');
    expect(highlighted.length).toBe(1);
  });

  it("sort tab list renders 4 options with 'recent' active", () => {
    renderWithQuery(<ReportsExportsTab />);
    const tabs = screen.getByRole("tablist", { name: "Archive sort" });
    expect(tabs.querySelectorAll("[role='tab']").length).toBe(4);
    expect(screen.getByRole("tab", { name: "Most recent" }).getAttribute("aria-selected")).toBe("true");
  });

  it("clicking 'Oldest' sort reorders the archive", () => {
    renderWithQuery(<ReportsExportsTab />);
    fireEvent.click(screen.getByRole("tab", { name: "Oldest" }));
    expect(screen.getByRole("tab", { name: "Oldest" }).getAttribute("aria-selected")).toBe("true");
    const cards = document.querySelectorAll("[data-report-id]");
    expect(cards.length).toBe(6);
    // Oldest first: r3 (2026-04-02) should be earlier in DOM than r2 (2026-05-18)
    const ids = Array.from(cards).map((c) => c.getAttribute("data-report-id"));
    expect(ids.indexOf("r3")).toBeLessThan(ids.indexOf("r2"));
  });

  it("renders + NEW REPORT button (outline-violet)", () => {
    renderWithQuery(<ReportsExportsTab />);
    expect(screen.getByRole("button", { name: /\+ NEW REPORT/ })).toBeInTheDocument();
  });

  it("generating card disables its DOWNLOAD button", () => {
    renderWithQuery(<ReportsExportsTab />);
    // r5 is the generating one
    const generatingCard = document.querySelector('[data-report-id="r5"]');
    expect(generatingCard).not.toBeNull();
    const dl = generatingCard?.querySelector('button[aria-label^="Download"]') as HTMLButtonElement | null;
    expect(dl?.hasAttribute("disabled")).toBe(true);
  });
});
