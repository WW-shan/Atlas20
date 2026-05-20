import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  it("renders children when nothing throws", () => {
    render(
      <ErrorBoundary>
        <div>Healthy child</div>
      </ErrorBoundary>,
    );

    expect(screen.getByText("Healthy child")).toBeInTheDocument();
  });

  it("renders an error banner and reload button when a child throws during render", () => {
    function Boom(): never {
      throw new Error("render failed");
    }

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Unable to render this view");
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
  });

  it("does not swallow event handler errors", () => {
    const onError = vi.fn();
    window.addEventListener("error", onError);

    render(
      <ErrorBoundary>
        <button
          type="button"
          onClick={() => {
            throw new Error("handler boom");
          }}
        >
          Explode
        </button>
      </ErrorBoundary>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Explode" }));

    expect(onError).toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    window.removeEventListener("error", onError);
  });
});
