import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Pill } from "./Pill";
import { StatusDot } from "./StatusDot";
import { KpiTile } from "./KpiTile";
import { SectionHeader } from "./SectionHeader";
import { Card } from "./Card";
import { Button } from "./Button";
import { Pager } from "./Pager";
import { EmptyState } from "./EmptyState";
import { ErrorBanner } from "./ErrorBanner";
import { Skeleton } from "./Skeleton";

describe("Pill", () => {
  it("renders text with correct role", () => {
    render(<Pill tone="emerald">COMPLETED</Pill>);
    expect(screen.getByRole("status")).toHaveTextContent("COMPLETED");
  });

  it("renders pulse dot when pulse=true", () => {
    const { container } = render(<Pill tone="cyan" pulse>RUNNING</Pill>);
    const dot = container.querySelector("span > span");
    expect(dot).toBeTruthy();
  });
});

describe("StatusDot", () => {
  it("renders a dot", () => {
    const { container } = render(<StatusDot tone="emerald" />);
    expect(container.querySelector("span")).toBeTruthy();
  });
});

describe("KpiTile", () => {
  it("renders label and value", () => {
    render(<KpiTile label="SHARPE" value="3.42" />);
    expect(screen.getByText("SHARPE")).toBeInTheDocument();
    expect(screen.getByText("3.42")).toBeInTheDocument();
  });

  it("renders inline variant", () => {
    render(<KpiTile label="CAGR" value="158.4%" inline />);
    expect(screen.getByText("158.4%")).toBeInTheDocument();
  });
});

describe("SectionHeader", () => {
  it("renders uppercase label", () => {
    render(<SectionHeader>STRATEGY</SectionHeader>);
    expect(screen.getByText("STRATEGY")).toBeInTheDocument();
  });
});

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Hello</Card>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("renders hero variant with card--hero class", () => {
    const { container } = render(<Card variant="hero">Hero</Card>);
    expect(container.querySelector(".card--hero")).toBeTruthy();
  });
});

describe("Button", () => {
  it("renders gold variant", () => {
    render(<Button variant="gold">RUN</Button>);
    expect(screen.getByRole("button", { name: "RUN" })).toBeInTheDocument();
  });

  it("shows spinner when loading", () => {
    render(<Button variant="gold" loading>Loading</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});

describe("Pager", () => {
  it("renders page buttons", () => {
    render(<Pager total={14} page={1} pageSize={14} onChange={() => {}} />);
    expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
  });
});

describe("EmptyState", () => {
  it("renders title and action", () => {
    render(<EmptyState title="No runs" action={{ label: "+ Add", onClick: () => {} }} />);
    expect(screen.getByRole("status")).toHaveTextContent("No runs");
    expect(screen.getByRole("button", { name: "+ Add" })).toBeInTheDocument();
  });
});

describe("ErrorBanner", () => {
  it("renders error message with retry", () => {
    render(<ErrorBanner message="Fetch failed" onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Fetch failed");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

describe("Skeleton", () => {
  it("renders shimmer placeholder", () => {
    const { container } = render(<Skeleton variant="chart" />);
    expect(container.querySelector("[aria-busy='true']")).toBeTruthy();
  });
});
