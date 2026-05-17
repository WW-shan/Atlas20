import { render, screen } from "@testing-library/react";

import App from "../App";


test("renders Atlas20 Research Console shell", () => {
  render(<App />);

  expect(screen.getByText(/Atlas20 Research Console/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Dashboard" })).toBeInTheDocument();
});
