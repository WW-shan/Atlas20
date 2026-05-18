import type { ReportThumbKind } from "../../lib/api";

type Props = {
  kind: ReportThumbKind;
};

// Minimal abstract glyphs — keep tones violet/cyan/muted so the gold
// remains reserved for hero chart + best-cell tint (SPEC §1.1).
export function ReportThumbnail({ kind }: Props) {
  return (
    <svg
      width="100%"
      height="96"
      viewBox="0 0 200 96"
      role="img"
      aria-label={`Report thumbnail · ${kind}`}
      style={{ display: "block", background: "rgba(139,92,246,0.04)" }}
    >
      {kind === "equity" && (
        <path
          d="M4 78 L40 64 L80 52 L120 38 L160 22 L196 12"
          fill="none"
          stroke="var(--violet)"
          strokeWidth="2"
          strokeLinecap="round"
        />
      )}
      {kind === "lines" && (
        <>
          <path d="M4 70 L40 60 L80 50 L120 40 L160 32 L196 24" fill="none" stroke="var(--violet)" strokeWidth="1.5" />
          <path d="M4 80 L40 76 L80 70 L120 64 L160 60 L196 58" fill="none" stroke="var(--cyan)"   strokeWidth="1.5" />
          <path d="M4 86 L40 82 L80 80 L120 78 L160 78 L196 76" fill="none" stroke="var(--muted)"  strokeWidth="1.2" strokeDasharray="3 3" />
        </>
      )}
      {kind === "heatmap" && Array.from({ length: 5 * 9 }).map((_, i) => {
        const col = i % 9;
        const row = Math.floor(i / 9);
        const t = (col + row) / 12;
        const r = Math.round(6 + (139 - 6) * t);
        const g = Math.round(182 + (92 - 182) * t);
        const b = Math.round(212 + (246 - 212) * t);
        return (
          <rect
            key={i}
            x={4 + col * 22}
            y={6 + row * 17}
            width={20}
            height={15}
            rx={2}
            fill={`rgba(${r}, ${g}, ${b}, 0.45)`}
          />
        );
      })}
      {kind === "bars" && Array.from({ length: 9 }).map((_, i) => {
        const h = 20 + ((i * 9) % 56);
        return (
          <rect
            key={i}
            x={6 + i * 22}
            y={88 - h}
            width={14}
            height={h}
            rx={1}
            fill="var(--violet)"
            opacity={0.7}
          />
        );
      })}
      {kind === "horizontal-bars" && Array.from({ length: 5 }).map((_, i) => {
        const w = 60 + ((i * 23) % 120);
        return (
          <rect
            key={i}
            x={6}
            y={12 + i * 16}
            width={w}
            height={10}
            rx={1}
            fill="var(--violet)"
            opacity={0.65}
          />
        );
      })}
      {kind === "sparkbar" && Array.from({ length: 14 }).map((_, i) => {
        const h = 20 + ((i * 11) % 48);
        return (
          <rect
            key={i}
            x={6 + i * 14}
            y={86 - h}
            width={10}
            height={h}
            rx={1}
            fill={i % 3 === 0 ? "var(--cyan)" : "var(--violet)"}
            opacity={0.7}
          />
        );
      })}
    </svg>
  );
}
