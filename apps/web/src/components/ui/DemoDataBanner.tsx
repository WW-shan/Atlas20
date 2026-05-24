interface Props {
  visible: boolean;
}

export function DemoDataBanner({ visible }: Props) {
  if (!visible) return null;
  return (
    <div
      role="alert"
      style={{
        background: "var(--amber-bg, rgba(251, 191, 36, 0.1))",
        border: "1px solid var(--amber, #fbbf24)",
        borderRadius: 8,
        padding: "10px 16px",
        marginBottom: 16,
        fontSize: 13,
        color: "var(--text-secondary, #a1a1aa)",
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 16, lineHeight: 1 }}>⚠</span>
      <span>
        <strong style={{ color: "var(--amber, #fbbf24)" }}>DEMO DATA</strong> — Showing cached
        examples. Run a backtest or seed the database to see real research data.
      </span>
    </div>
  );
}
