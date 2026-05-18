type RegimeGaugeProps = {
  label: "RISK-ON" | "NEUTRAL" | "RISK-OFF";
  score: number; // 0..1
  model: string;
};

export function RegimeGauge({ label, score, model }: RegimeGaugeProps) {
  // score 0 = full rose, 0.5 = muted, 1 = full emerald
  const indicatorX = Math.max(0, Math.min(1, score)) * 100;

  const labelColor =
    label === "RISK-ON" ? "var(--gold)" :
    label === "RISK-OFF" ? "var(--rose)" : "var(--muted)";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: "0.04em",
          color: labelColor,
        }}
        aria-label={`Market regime: ${label}, score ${score.toFixed(2)}`}
      >
        {label}
      </span>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={score}
        aria-label={`Regime score ${score.toFixed(2)}`}
        style={{
          position: "relative",
          height: 8,
          background: "linear-gradient(to right, var(--rose), var(--muted), var(--emerald))",
          borderRadius: 4,
        }}
      >
        <div
          style={{
            position: "absolute",
            left: `${indicatorX}%`,
            top: -2,
            width: 2,
            height: 12,
            background: "var(--text)",
            transform: "translateX(-1px)",
          }}
        />
      </div>
      <span className="muted" style={{ fontSize: 11 }}>
        Risk model · <span className="mono">{model}</span> · regime score{" "}
        <span className="mono">{score.toFixed(2)}</span>
      </span>
    </div>
  );
}
