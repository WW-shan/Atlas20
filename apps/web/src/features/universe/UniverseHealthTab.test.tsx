import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { UniverseHealthTab } from "./UniverseHealthTab";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    refreshUniverse: vi.fn(),
  };
});

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.refreshUniverse).mockResolvedValue({ refreshed_at: "2026-05-20T00:00:00Z" });
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

  it("keeps universe data visible after a refresh failure", async () => {
    vi.mocked(api.refreshUniverse).mockRejectedValueOnce(new Error("refresh failed"));

    renderWithQuery(<UniverseHealthTab />);
    const button = screen.getByRole("button", { name: /FORCE REFRESH/ });
    fireEvent.click(button);

    await waitFor(() => expect(api.refreshUniverse).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(button).not.toBeDisabled());
    expect(screen.getByRole("list", { name: "Data sources" }).querySelectorAll("[role='listitem']")).toHaveLength(9);
  });
});
