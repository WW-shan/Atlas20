import type { ReactNode } from "react";

export type ButtonVariant = "gold" | "outline-gold" | "outline-violet" | "outline-muted" | "outline-dashed" | "ghost";

export type ButtonProps = {
  variant: ButtonVariant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
};

const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
  gold: {
    background: "var(--gold)",
    color: "var(--bg)",
    border: "none",
    fontWeight: 700,
    boxShadow: "0 0 16px var(--gold-glow)",
  },
  "outline-gold": {
    background: "transparent",
    color: "var(--gold)",
    border: "1px solid var(--gold)",
  },
  "outline-violet": {
    background: "transparent",
    color: "var(--violet)",
    border: "1px solid var(--violet)",
  },
  "outline-muted": {
    background: "transparent",
    color: "var(--muted)",
    border: "1px solid var(--border)",
  },
  "outline-dashed": {
    background: "transparent",
    color: "var(--muted)",
    border: "1px dashed var(--border)",
  },
  ghost: {
    background: "transparent",
    color: "var(--muted)",
    border: "none",
  },
};

const sizeStyles: Record<string, React.CSSProperties> = {
  sm: { padding: "4px 12px", fontSize: 11, minHeight: 28 },
  md: { padding: "6px 16px", fontSize: 13, minHeight: 34 },
  lg: { padding: "8px 20px", fontSize: 14, minHeight: 40 },
};

export function Button({ variant, size = "md", loading, disabled, onClick, children }: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        borderRadius: "var(--radius-input)",
        cursor: disabled ? "not-allowed" : "pointer",
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        opacity: disabled ? 0.5 : 1,
        ...variantStyles[variant],
        ...sizeStyles[size],
      }}
    >
      {loading && (
        <span style={{ animation: "spin 0.8s linear infinite", display: "inline-block" }}>↻</span>
      )}
      {children}
    </button>
  );
}
