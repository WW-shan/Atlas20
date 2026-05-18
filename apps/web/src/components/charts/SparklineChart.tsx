export type SparkTone = "violet" | "cyan" | "emerald" | "rose" | "gold" | "muted-dashed";

export type SparklineProps = {
  points: number[];
  tone: SparkTone;
  height?: number;
  width?: number;
  ariaLabel?: string;
};

const toneColors: Record<SparkTone, string> = {
  violet:  "var(--violet)",
  cyan:    "var(--cyan)",
  emerald: "var(--emerald)",
  rose:    "var(--rose)",
  gold:    "var(--gold)",
  "muted-dashed": "var(--muted)",
};

function pointsToPath(values: number[], width: number, height: number) {
  if (values.length === 0) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values
    .map((v, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function SparklineChart({ points, tone, height = 24, width = 120, ariaLabel }: SparklineProps) {
  const path = pointsToPath(points, width, height);
  const stroke = toneColors[tone];
  const dashed = tone === "muted-dashed";

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={ariaLabel ?? "Sparkline"}
      style={{ display: "block" }}
    >
      <path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={dashed ? "3 3" : undefined}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
