export type SkeletonProps = {
  variant: "text" | "chart" | "table" | "card";
  width?: string;
  height?: string;
};

const defaults: Record<string, { width: string; height: string }> = {
  text:  { width: "100%", height: "14px" },
  chart: { width: "100%", height: "200px" },
  table: { width: "100%", height: "300px" },
  card:  { width: "100%", height: "180px" },
};

export function Skeleton({ variant, width, height }: SkeletonProps) {
  const d = defaults[variant];
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading"
      data-variant={variant}
      style={{
        width: width ?? d.width,
        height: height ?? d.height,
        borderRadius: variant === "card" ? "var(--radius-card)" : 4,
        background: "linear-gradient(90deg, var(--surface) 25%, var(--surface-2) 50%, var(--surface) 75%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.2s ease-in-out infinite",
      }}
    />
  );
}
