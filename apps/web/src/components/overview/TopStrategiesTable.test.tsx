import { render, screen } from "@testing-library/react";

import { TopStrategiesTable } from "./TopStrategiesTable";


test("renders strategy ranking rows", () => {
  render(
    <TopStrategiesTable
      rows={[
        {
          strategy: "Champion",
          multiple: 237,
          cagr: 3.94,
          sharpe: 2.29,
          max_drawdown: -0.5,
        },
      ]}
    />,
  );

  expect(screen.getByText("Champion")).toBeInTheDocument();
  expect(screen.getByText("237.00x")).toBeInTheDocument();
});
