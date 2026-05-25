import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fallbackRunDetail } from "../../lib/api";
import { EquityWorkspace } from "./EquityWorkspace";

describe("EquityWorkspace", () => {
  it("lets users switch artifact tabs and renders backend rows", () => {
    const detail = {
      ...fallbackRunDetail,
      selected_strategy: "Mean Reversion v2",
      drawdown_series: [
        { ts: "2026-01-01", atlas: 0, btc: 0 },
        { ts: "2026-01-02", atlas: -12, btc: -5 },
      ],
      return_series: [
        { ts: "2026-01-01", atlas: 0, btc: 0 },
        { ts: "2026-01-02", atlas: 2, btc: 1 },
      ],
      turnover_rows: [
        {
          strategy: "Mean Reversion v2",
          annualized_turnover: 1.5,
          avg_turnover_per_rebalance: 0.25,
          average_holdings: 4,
        },
      ],
      trade_rows: [
        {
          rebalance_date: "2026-01-15",
          strategy: "Mean Reversion v2",
          coin_id: "solana",
          coin_rank: 1,
          coin_score: 0.91,
          coin_weight: 0.5,
        },
      ],
    };

    render(<EquityWorkspace detail={detail} />);

    const drawdownTab = screen.getByRole("tab", { name: "Drawdown" });
    expect(drawdownTab).not.toBeDisabled();

    fireEvent.click(drawdownTab);
    expect(drawdownTab).toHaveAttribute("aria-selected", "true");

    fireEvent.click(screen.getByRole("tab", { name: "Turnover" }));
    expect(screen.getByText("Annualized Turnover")).toBeInTheDocument();
    expect(screen.getByText("150.0%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Trades" }));
    expect(screen.getByText("solana")).toBeInTheDocument();
  });
});
