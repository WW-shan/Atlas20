import type { ChartRange } from "../ui/types";

export type OverlayLineTone = "gold" | "violet" | "cyan" | "emerald" | "rose" | "muted";

export type OverlayLine = {
  id: string;
  label: string;
  tone: OverlayLineTone;
  glow?: boolean;
  dashed?: boolean;
};

type Series = { ts: string; values: Record<string, number> }[];

export type OverlayLineChartProps = {
  series: Series;
  lines: OverlayLine[];
  range: ChartRange;
  yFormat?: "percent" | "absolute" | "compact";
  annotations?: { ts: string; label: string; tone?: "gold" | "violet" }[];
  height?: number;
  ariaLabel?: string;
};

const toneColors: Record<OverlayLineTone, string> = {
  gold: "var(--gold)",
  violet: "var(--violet)",
  cyan: "var(--cyan)",
  emerald: "var(--emerald)",
  rose: "var(--rose)",
  muted: "var(--muted)",
};

function formatY(v: number, fmt: OverlayLineChartProps["yFormat"]): string {
  if (fmt === "percent") return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
  if (fmt === "compact") {
    if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
    return v.toFixed(0);
  }
  return v.toFixed(2);
}

export function OverlayLineChart({
  series,
  lines,
  range,
  yFormat = "percent",
  annotations = [],
  height = 320,
  ariaLabel,
}: OverlayLineChartProps) {
  const width = 1000;
  const padding = { top: 16, right: 24, bottom: 32, left: 56 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  if (series.length === 0 || lines.length === 0) {
    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={ariaLabel ?? "Empty chart"}
        style={{ width: "100%", height }}
      />
    );
  }

  // Compute bounds across all visible lines
  let minY = Infinity;
  let maxY = -Infinity;
  for (const point of series) {
    for (const line of lines) {
      const v = point.values[line.id];
      if (typeof v === "number") {
        if (v < minY) minY = v;
        if (v > maxY) maxY = v;
      }
    }
  }
  if (minY === Infinity) { minY = 0; maxY = 1; }
  if (minY === maxY) { maxY = minY + 1; }

  const xOf = (i: number) => padding.left + (i / Math.max(series.length - 1, 1)) * innerW;
  const yOf = (v: number) => padding.top + innerH - ((v - minY) / (maxY - minY)) * innerH;

  const yTicks = 4;
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => minY + ((maxY - minY) * i) / yTicks);

  const pathFor = (lineId: string) => {
    const pts = series.map((p, i) => {
      const v = p.values[lineId];
      return typeof v === "number" ? `${i === 0 ? "M" : "L"} ${xOf(i).toFixed(2)} ${yOf(v).toFixed(2)}` : "";
    });
    return pts.filter(Boolean).join(" ");
  };

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel ?? `Overlay chart, range ${range}, ${lines.length} series`}
      style={{ width: "100%", height, display: "block" }}
    >
      <defs>
        <filter id="gold-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Y-axis gridlines + labels */}
      {ticks.map((t, i) => (
        <g key={`tick-${i}`}>
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={yOf(t)}
            y2={yOf(t)}
            stroke="var(--border)"
            strokeWidth="1"
            strokeDasharray={i === 0 ? undefined : "2 4"}
            opacity={i === 0 ? 1 : 0.4}
          />
          <text
            x={padding.left - 8}
            y={yOf(t) + 4}
            textAnchor="end"
            fontFamily="var(--font-mono)"
            fontSize="11"
            fill="var(--muted)"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formatY(t, yFormat)}
          </text>
        </g>
      ))}

      {/* X-axis labels (first / mid / last) */}
      {Array.from(new Set([0, Math.floor(series.length / 2), Math.max(0, series.length - 1)])).map((i) => (
        <text
          key={`xl-${i}`}
          x={xOf(i)}
          y={height - padding.bottom + 18}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize="11"
          fill="var(--muted)"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {series[i]?.ts ?? ""}
        </text>
      ))}

      {/* Annotations (vertical lines) */}
      {annotations.map((a, i) => {
        const idx = series.findIndex((s) => s.ts === a.ts);
        if (idx < 0) return null;
        const color = a.tone === "gold" ? "var(--gold)" : "var(--violet)";
        return (
          <g key={`ann-${i}`}>
            <line
              x1={xOf(idx)}
              x2={xOf(idx)}
              y1={padding.top}
              y2={height - padding.bottom}
              stroke={color}
              strokeWidth="1"
              strokeDasharray="3 3"
              opacity="0.6"
            />
            <text
              x={xOf(idx)}
              y={padding.top - 4}
              textAnchor="middle"
              fontFamily="var(--font-mono)"
              fontSize="10"
              fill={color}
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {a.label}
            </text>
          </g>
        );
      })}

      {/* Lines */}
      {lines.map((line) => (
        <path
          key={line.id}
          d={pathFor(line.id)}
          fill="none"
          stroke={toneColors[line.tone]}
          strokeWidth={line.glow ? "2" : "1.5"}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={line.dashed ? "4 4" : undefined}
          filter={line.glow && line.tone === "gold" ? "url(#gold-glow)" : undefined}
          opacity={line.tone === "muted" ? 0.5 : 1}
        />
      ))}
    </svg>
  );
}
