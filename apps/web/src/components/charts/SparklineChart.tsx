import type { SeriesPoint } from "../../lib/api";

function pointsToPath(points: SeriesPoint[], width: number, height: number) {
  if (points.length === 0) return "";
  const values = points.map((point) => point.value);
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
  points: SeriesPoint[];
  tone?: "equity" | "drawdown";
}) {
  const width = 720;
  const height = 240;
  const path = pointsToPath(props.points, width, height);
  return (
    <svg className={`sparkline sparkline--${props.tone ?? "equity"}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Time series chart">
      <defs>
        <linearGradient id={`line-${props.tone ?? "equity"}`} x1="0" x2="1">
          <stop offset="0%" stopColor="#39d98a" />
          <stop offset="55%" stopColor="#42a5ff" />
          <stop offset="100%" stopColor="#f2b84b" />
        </linearGradient>
      </defs>
      <rect width={width} height={height} rx="10" />
      <path d={path} />
    </svg>
  );
}
