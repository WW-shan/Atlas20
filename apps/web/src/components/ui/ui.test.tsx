import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Pill } from "./Pill";
import { PillButton } from "./PillButton";
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
  it("renders text with status role", () => {
    render(<Pill tone="emerald">COMPLETED</Pill>);
    expect(screen.getByRole("status")).toHaveTextContent("COMPLETED");
  });

  it("renders pulse dot when pulse=true", () => {
    const { container } = render(<Pill tone="cyan" pulse>RUNNING</Pill>);
    const dot = container.querySelector("span > span");
    expect(dot).toBeTruthy();
  });
});

describe("PillButton", () => {
  it("renders as button with aria-pressed when active", () => {
    render(<PillButton tone="violet" active>MARKDOWN</PillButton>);
    expect(screen.getByRole("button", { name: "MARKDOWN" })).toHaveAttribute("aria-pressed", "true");
  });

  it("calls onClick", () => {
    let clicked = false;
    render(<PillButton tone="gold" onClick={() => { clicked = true; }}>PDF</PillButton>);
    screen.getByRole("button", { name: "PDF" }).click();
    expect(clicked).toBe(true);
  });
});

describe("StatusDot", () => {
  it("renders presentational dot with data-tone", () => {
    const { container } = render(<StatusDot tone="emerald" />);
    const dot = container.querySelector("span");
    expect(dot).toBeTruthy();
    expect(dot?.getAttribute("data-tone")).toBe("emerald");
    expect(dot?.getAttribute("aria-hidden")).toBe("true");
  });
});

describe("KpiTile", () => {
  it("renders as accessible group with label", () => {
    render(<KpiTile label="SHARPE" value="3.42" />);
    expect(screen.getByRole("group", { name: "SHARPE" })).toBeInTheDocument();
    expect(screen.getByText("3.42")).toBeInTheDocument();
  });

  it("inline variant renders label + value + delta together", () => {
    render(<KpiTile label="CAGR" value="158.4%" delta={{ value: "+12.3%", tone: "emerald" }} inline />);
    const group = screen.getByRole("group", { name: "CAGR" });
    expect(group).toHaveTextContent("CAGR");
    expect(group).toHaveTextContent("158.4%");
    expect(group).toHaveTextContent("+12.3%");
  });
});

describe("SectionHeader", () => {
  it("renders as heading with level 3", () => {
    render(<SectionHeader>STRATEGY</SectionHeader>);
    expect(screen.getByRole("heading", { level: 3, name: "STRATEGY" })).toBeInTheDocument();
  });
});

describe("Card", () => {
  it("renders as section with optional aria-label", () => {
    render(<Card ariaLabel="Hero card">Hello</Card>);
    expect(screen.getByRole("region", { name: "Hero card" })).toBeInTheDocument();
  });

  it("renders hero variant with card--hero class", () => {
    const { container } = render(<Card variant="hero">Hero</Card>);
    expect(container.querySelector(".card--hero")).toBeTruthy();
    expect(container.querySelector("[data-variant='hero']")).toBeTruthy();
  });

  it("renders report variant with thumbnail slot", () => {
    const { container } = render(
      <Card variant="report" thumbnail={<div data-testid="thumb">📊</div>}>Body</Card>
    );
    expect(container.querySelector(".card--report")).toBeTruthy();
    expect(screen.getByTestId("thumb")).toBeInTheDocument();
  });
});

describe("Button", () => {
  it("renders gold variant", () => {
    render(<Button variant="gold">RUN</Button>);
    expect(screen.getByRole("button", { name: "RUN" })).toBeInTheDocument();
  });

  it("shows spinner when loading and is disabled", () => {
    render(<Button variant="gold" loading>Loading</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("outline-dashed variant exists", () => {
    render(<Button variant="outline-dashed">+ Add strategy</Button>);
    expect(screen.getByRole("button", { name: "+ Add strategy" })).toBeInTheDocument();
  });
});

describe("Pager", () => {
  it("renders page buttons with aria-current", () => {
    render(<Pager total={14} page={1} pageSize={14} onChange={() => {}} />);
    expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
  });

  it("displays Showing X-Y of Z with mono numbers", () => {
    const { container } = render(<Pager total={284} page={1} pageSize={14} onChange={() => {}} />);
    const nav = container.querySelector("[role='navigation']");
    expect(nav).toHaveTextContent(/Showing.*1.*14.*of.*284/);
    // 3 mono spans in the showing range: from, to, total
    const monoSpans = nav?.querySelectorAll("span.mono");
    expect(monoSpans?.length).toBeGreaterThanOrEqual(3);
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
  it("renders with aria-busy and aria-label", () => {
    render(<Skeleton variant="chart" />);
    const sk = screen.getByRole("status", { name: "Loading" });
    expect(sk).toHaveAttribute("aria-busy", "true");
  });

  it("supports 4 variants", () => {
    for (const variant of ["text", "chart", "table", "card"] as const) {
      const { container, unmount } = render(<Skeleton variant={variant} />);
      expect(container.querySelector(`[data-variant='${variant}']`)).toBeTruthy();
      unmount();
    }
  });
});
