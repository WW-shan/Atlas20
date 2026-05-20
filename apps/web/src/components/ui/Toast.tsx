import type { ReactNode } from "react";

type ToastProps = {
  children: ReactNode;
};

export function Toast({ children }: ToastProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      style={{
        alignSelf: "flex-end",
        padding: "8px 12px",
        borderRadius: "var(--radius-input)",
        border: "1px solid rgba(34,197,94,0.35)",
        background: "rgba(34,197,94,0.10)",
        color: "var(--text)",
        fontSize: 12,
        fontWeight: 700,
      }}
    >
      {children}
    </div>
  );
}
