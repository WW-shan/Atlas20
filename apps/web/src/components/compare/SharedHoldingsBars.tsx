type Props = {
  holdings: { symbol: string; count: number; total: number }[];
};

export function SharedHoldingsBars({ holdings }: Props) {
  return (
    <div
      role="list"
      aria-label="Top shared holdings"
      style={{ display: "flex", flexDirection: "column", gap: 10 }}
    >
      {holdings.map((h) => {
        const pct = h.total > 0 ? Math.min(1, h.count / h.total) : 0;
        return (
          <div
            key={h.symbol}
            role="listitem"
            data-symbol={h.symbol}
            style={{
              display: "grid",
              gridTemplateColumns: "44px 1fr auto",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span
              className="mono"
              style={{
                fontSize: 12,
                color: "var(--text)",
                letterSpacing: "0.04em",
              }}
            >
              {h.symbol}
            </span>
            <div
              style={{
                position: "relative",
                height: 8,
                background: "rgba(139,92,246,0.10)",
                borderRadius: 4,
                overflow: "hidden",
              }}
              aria-label={`${h.symbol} appears in ${h.count} of ${h.total} strategies`}
            >
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: `${pct * 100}%`,
                  background: "var(--violet)",
                  borderRadius: 4,
                }}
              />
            </div>
            <span
              className="mono"
              style={{
                fontSize: 11,
                color: "var(--muted)",
                whiteSpace: "nowrap",
              }}
            >
              {h.count}/{h.total}
            </span>
          </div>
        );
      })}
    </div>
  );
}
