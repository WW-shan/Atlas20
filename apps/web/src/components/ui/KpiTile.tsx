import { SparklineChart } from "../charts/SparklineChart";

export type KpiTileProps = {
  label: string;
  value: string | number;
  delta?: { value: string; tone: "emerald" | "rose" | "muted" };
  spark?: { points: number[]; tone: "violet" | "cyan" | "emerald" | "rose" };
  inline?: boolean;
};

const deltaColors = {
  emerald: "var(--emerald)",
  rose: "var(--rose)",
  muted: "var(--muted)",
};

export function KpiTile({ label, value, delta, spark, inline }: KpiTileProps) {
  if (inline) {
    return (
      <span role="group" aria-label={label} style={{ display: "inline-flex", alignItems: "baseline", gap: 8 }}>
        <span
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 14,
            fontWeight: 600,
            letterSpacing: "0.08em",
            textTransform: "uppercase" as const,
            color: "var(--muted)",
          }}
        >
          {label}
        </span>
        <span className="mono" style={{ fontSize: 16 }}>{value}</span>
        {delta && (
          <span className="mono" style={{ fontSize: 12, color: deltaColors[delta.tone] }}>
            {delta.value}
          </span>
        )}
      </span>
    );
  }

  return (
    <div role="group" aria-label={label} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase" as const,
          color: "var(--muted)",
        }}
      >
        {label}
      </span>
      <span className="mono" style={{ fontSize: 24, lineHeight: 1 }}>{value}</span>
      {spark && (
        <SparklineChart
          points={spark.points}
          tone={spark.tone}
          height={24}
          width={120}
          ariaLabel={`${label} trend`}
        />
      )}
      {delta && (
        <span className="mono" style={{ fontSize: 13, color: deltaColors[delta.tone] }}>
          {delta.value}
        </span>
      )}
    </div>
  );
}
