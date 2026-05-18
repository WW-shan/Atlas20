import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UniverseHealthTab } from "./UniverseHealthTab";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("UniverseHealthTab", () => {
  it("renders Universe Timeline svg with aria-label", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(screen.getByRole("img", { name: /Universe composition timeline/ })).toBeInTheDocument();
  });

  it("renders FORCE REFRESH button (outline-violet)", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(screen.getByRole("button", { name: /FORCE REFRESH/ })).toBeInTheDocument();
  });

  it("renders 9 data source tiles", () => {
    renderWithQuery(<UniverseHealthTab />);
    const list = screen.getByRole("list", { name: "Data sources" });
    const items = list.querySelectorAll("[role='listitem']");
    expect(items.length).toBe(9);
  });

  it("renders status mix 6 healthy / 2 degraded / 1 error", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(document.querySelectorAll('[data-status="healthy"]').length).toBe(6);
    expect(document.querySelectorAll('[data-status="degraded"]').length).toBe(2);
    expect(document.querySelectorAll('[data-status="error"]').length).toBe(1);
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

  it("DATA ALERTS section badge shows '6 OPEN'", () => {
    renderWithQuery(<UniverseHealthTab />);
    expect(screen.getByText("6 OPEN")).toBeInTheDocument();
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
});
