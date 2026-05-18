import type { SeriesPoint } from "../../lib/api";

type SparkTone = "violet" | "cyan" | "emerald" | "rose" | "gold" | "muted-dashed";

const toneColors: Record<SparkTone, string> = {
  violet:  "var(--violet)",
  cyan:    "var(--cyan)",
  emerald: "var(--emerald)",
  rose:    "var(--rose)",
  gold:    "var(--gold)",
  "muted-dashed": "var(--muted)",
};

type Point = SeriesPoint | { value: number };

function pointsToPath(points: Point[], width: number, height: number) {
  if (points.length === 0) return "";
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width;
      const y = height - ((point.value - min) / range) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function SparklineChart(props: {
  points: Point[] | number[];
  tone?: SparkTone;
  height?: number;
  width?: number;
  ariaLabel?: string;
}) {
  const tone: SparkTone = props.tone ?? "violet";
  const width = props.width ?? 120;
  const height = props.height ?? 32;

  const points: Point[] = Array.isArray(props.points) && typeof props.points[0] === "number"
    ? (props.points as number[]).map((v) => ({ value: v }))
    : (props.points as Point[]);

  const path = pointsToPath(points, width, height);
  const stroke = toneColors[tone];
  const dashed = tone === "muted-dashed";

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={props.ariaLabel ?? "Sparkline"}
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
