type StrategyBarRowProps = {
  family: string;
  count: number;
  max: number;
};

export function StrategyBarRow({ family, count, max }: StrategyBarRowProps) {
  const widthPct = (count / Math.max(max, 1)) * 100;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 32px", alignItems: "center", gap: 8 }}>
      <span style={{ fontSize: 12, color: "var(--muted)" }}>{family}</span>
      <div
        style={{
          height: 6,
          background: "var(--border)",
          borderRadius: 3,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${widthPct}%`,
            height: "100%",
            background: "var(--violet)",
            borderRadius: 3,
          }}
        />
      </div>
      <span className="mono" style={{ fontSize: 12, textAlign: "right" }}>{count}</span>
    </div>
  );
}
