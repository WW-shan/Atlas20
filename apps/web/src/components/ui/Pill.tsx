import type { PillTone } from "./types";

export type PillProps = {
  tone: PillTone;
  size?: "xs" | "sm" | "md";
  pulse?: boolean;
  live?: boolean;
  children: React.ReactNode;
};

const toneStyles: Record<PillTone, { color: string; bg: string; border: string }> = {
  emerald:       { color: "var(--emerald)", bg: "rgba(16,185,129,0.10)", border: "rgba(16,185,129,0.30)" },
  cyan:          { color: "var(--cyan)",    bg: "rgba(6,182,212,0.10)",  border: "rgba(6,182,212,0.30)" },
  rose:          { color: "var(--rose)",    bg: "rgba(244,63,94,0.10)",  border: "rgba(244,63,94,0.30)" },
  violet:        { color: "var(--violet)",  bg: "rgba(139,92,246,0.10)", border: "rgba(139,92,246,0.30)" },
  muted:         { color: "var(--muted)",   bg: "rgba(148,163,184,0.06)",border: "rgba(148,163,184,0.20)" },
  gold:          { color: "var(--gold)",    bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.35)" },
  "gold-outline":{ color: "var(--gold)",    bg: "transparent",           border: "var(--gold)" },
  "cyan-outline":{ color: "var(--cyan)",    bg: "transparent",           border: "var(--cyan)" },
  "violet-outline":{ color:"var(--violet)", bg: "transparent",           border: "var(--violet)" },
};

const sizeStyles: Record<string, { fontSize: string; padding: string }> = {
  xs: { fontSize: "10px", padding: "2px 8px" },
  sm: { fontSize: "11px", padding: "3px 10px" },
  md: { fontSize: "12px", padding: "5px 14px" },
};

export function Pill({ tone, size = "sm", pulse, live, children }: PillProps) {
  const s = toneStyles[tone];
  const sz = sizeStyles[size];
  const liveProps = live || pulse
    ? { role: "status", "aria-live": "polite" as const }
    : {};

  return (
    <span
      {...liveProps}
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
        background: s.bg,
        border: `1px solid ${s.border}`,
        fontSize: sz.fontSize,
        padding: sz.padding,
      }}
    >
      {pulse && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: s.color,
            animation: "pulse-ring 1.5s ease-in-out infinite",
          }}
        />
      )}
      {children}
    </span>
  );
}
