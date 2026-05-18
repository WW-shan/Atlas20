import { act, render, screen } from "@testing-library/react";

import App from "../App";

const tabNames = ["Overview", "Backtest", "Compare", "History", "Universe", "Reports"];

test("renders Atlas20 Research Console with 6 tabs", () => {
  render(<App />);

  expect(screen.getByText("ATLAS20")).toBeInTheDocument();

  for (const name of tabNames) {
    expect(screen.getByRole("tab", { name })).toBeInTheDocument();
  }

  const overviewTab = screen.getByRole("tab", { name: "Overview" });
  expect(overviewTab).toHaveAttribute("aria-selected", "true");
});

test("clicking tab switches content", async () => {
  render(<App />);

  const overviewTab = screen.getByRole("tab", { name: "Overview" });
  const reportsTab = screen.getByRole("tab", { name: "Reports" });

  act(() => { reportsTab.click(); });

  expect(reportsTab).toHaveAttribute("aria-selected", "true");
  expect(overviewTab).toHaveAttribute("aria-selected", "false");

  // Placeholder content shows (Reports still a placeholder until P10)
  expect(screen.getByText(/Coming soon/)).toBeInTheDocument();
});
