import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

export type DialogProps = {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  width?: number;
};

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function tabbableElements(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => {
    return !element.hasAttribute("disabled") && element.getAttribute("aria-hidden") !== "true";
  });
}

export function Dialog({ open, onClose, children, ariaLabel, ariaLabelledBy, width = 560 }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const panel = panelRef.current;
    if (!panel) return;
    const controls = tabbableElements(panel);
    (controls[0] ?? panel).focus();
    return () => {
      restoreFocusRef.current?.focus();
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const controls = tabbableElements(panel);
    if (controls.length === 0) {
      event.preventDefault();
      panel.focus();
      return;
    }
    const first = controls[0];
    const last = controls[controls.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
      return;
    }
    if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
      return;
    }
    if (!controls.includes(active as HTMLElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    }
  };

  return createPortal(
    <div
      data-dialog-overlay
      role="presentation"
      onKeyDown={handleKeyDown}
      // We use onMouseDown (not onClick) plus a currentTarget check.
      // This prevents accidental close when a user starts text-selection
      // inside the dialog panel and releases the mouse outside it: onClick
      // would fire on the backdrop and incorrectly close. mouseDown +
      // currentTarget guarantees the press began on the backdrop itself.
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        background: "rgba(2,6,23,0.72)",
        backdropFilter: "blur(4px)",
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        tabIndex={-1}
        data-dialog-panel
        style={{
          width: `min(${width}px, calc(100vw - 32px))`,
          maxHeight: "calc(100vh - 48px)",
          overflowY: "auto",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-card)",
          boxShadow: "0 24px 80px rgba(0,0,0,0.45)",
          color: "var(--text)",
        }}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
