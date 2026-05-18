import type { PillTone } from "./types";

export type StatusDotProps = { tone: PillTone; pulse?: boolean };

const toneColors: Record<PillTone, string> = {
  emerald: "var(--emerald)", cyan: "var(--cyan)", rose: "var(--rose)",
  violet: "var(--violet)", muted: "var(--muted)", gold: "var(--gold)",
  "gold-outline": "var(--gold)", "cyan-outline": "var(--cyan)",
  "violet-outline": "var(--violet)",
};

export function StatusDot({ tone, pulse }: StatusDotProps) {
  return (
    <span
      role="presentation"
      aria-hidden="true"
      data-tone={tone}
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: toneColors[tone],
        animation: pulse ? "pulse-ring 1.5s ease-in-out infinite" : undefined,
      }}
    />
  );
}
