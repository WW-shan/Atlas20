import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { defaultBacktestConfig } from "../../lib/api";
import { ParameterSidebar } from "./ParameterSidebar";

function renderSidebar(presets?: { slug: string; display_name: string }[]) {
  return render(
    <ParameterSidebar
      value={defaultBacktestConfig}
      onChange={vi.fn()}
      onRun={vi.fn()}
      isRunning={false}
      presets={presets}
    />,
  );
}

describe("ParameterSidebar", () => {
  it("offers only the selected preset while /api/options is unavailable", () => {
    renderSidebar(undefined);

    const select = screen.getByRole("combobox", { name: "Strategy preset" });
    const values = within(select).getAllByRole("option").map((option) => (option as HTMLOptionElement).value);
    expect(values).toEqual([defaultBacktestConfig.preset]);
  });

  it("pins the backtest universe to the point-in-time Top 20 (AGENTS.md constraint)", () => {
    renderSidebar(undefined);

    expect(screen.queryByRole("slider", { name: /Top-N/ })).not.toBeInTheDocument();
    expect(screen.getByText("N = 20")).toBeInTheDocument();
  });

  it("lists the presets returned by /api/options", () => {
    renderSidebar([
      { slug: "base", display_name: "Base Config" },
      { slug: "phase_momentum", display_name: "Phase Momentum" },
    ]);

    const select = screen.getByRole("combobox", { name: "Strategy preset" });
    expect(within(select).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Base Config",
      "Phase Momentum",
    ]);
  });
});
