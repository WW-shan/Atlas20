import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Dialog } from "./Dialog";

describe("Dialog", () => {
  it("renders an accessible modal dialog and closes on Escape", () => {
    const onClose = vi.fn();

    render(
      <Dialog open onClose={onClose} ariaLabel="Test dialog">
        <button type="button">First</button>
      </Dialog>,
    );

    const dialog = screen.getByRole("dialog", { name: "Test dialog" });
    expect(dialog).toHaveAttribute("aria-modal", "true");

    fireEvent.keyDown(dialog, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("traps Tab focus within tabbable dialog controls", () => {
    const onClose = vi.fn();

    render(
      <Dialog open onClose={onClose} ariaLabel="Focus dialog">
        <button type="button">First</button>
        <button type="button">Last</button>
      </Dialog>,
    );

    const dialog = screen.getByRole("dialog", { name: "Focus dialog" });
    const first = screen.getByRole("button", { name: "First" });
    const last = screen.getByRole("button", { name: "Last" });

    last.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(first).toHaveFocus();

    first.focus();
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });
});
