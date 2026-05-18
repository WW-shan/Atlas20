import type { PillTone } from "./types";

export type PillButtonProps = {
  tone: PillTone;
  size?: "sm" | "md";
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
};

const toneColors: Record<PillTone, { color: string; border: string; bg: string }> = {
  emerald:        { color: "var(--emerald)", border: "var(--emerald)", bg: "rgba(16,185,129,0.10)" },
  cyan:           { color: "var(--cyan)",    border: "var(--cyan)",    bg: "rgba(6,182,212,0.10)" },
  rose:           { color: "var(--rose)",    border: "var(--rose)",    bg: "rgba(244,63,94,0.10)" },
  violet:         { color: "var(--violet)",  border: "var(--violet)",  bg: "rgba(139,92,246,0.10)" },
  muted:          { color: "var(--muted)",   border: "var(--border)",  bg: "transparent" },
  gold:           { color: "var(--gold)",    border: "var(--gold)",    bg: "rgba(245,158,11,0.12)" },
  "gold-outline": { color: "var(--gold)",    border: "var(--gold)",    bg: "transparent" },
  "cyan-outline": { color: "var(--cyan)",    border: "var(--cyan)",    bg: "transparent" },
  "violet-outline": { color: "var(--violet)", border: "var(--violet)", bg: "transparent" },
};

const sizes = {
  sm: { fontSize: 12, padding: "6px 14px" },
  md: { fontSize: 13, padding: "8px 18px" },
};

export function PillButton({ tone, size = "md", active, onClick, children }: PillButtonProps) {
  const s = toneColors[tone];
  const sz = sizes[size];
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active ?? undefined}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        borderRadius: "var(--radius-pill)",
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        color: s.color,
        background: active ? s.bg : "transparent",
        border: `1px solid ${s.border}`,
        cursor: "pointer",
        fontSize: sz.fontSize,
        padding: sz.padding,
        transition: "background 0.15s",
      }}
    >
      {children}
    </button>
  );
}
