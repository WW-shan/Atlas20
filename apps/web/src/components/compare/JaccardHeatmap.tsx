import { Fragment } from "react";

type Props = {
  symbols: string[];
  matrix: number[][];
};

function cellStyle(value: number, isDiagonal: boolean): React.CSSProperties {
  if (isDiagonal) {
    return {
      background: "var(--gold)",
      color: "var(--bg)",
      fontWeight: 700,
    };
  }
  // Non-diagonal: violet → cyan gradient based on value (0..1)
  // Low overlap = cyan, high overlap = violet
  const t = Math.max(0, Math.min(1, value));
  const r = Math.round(6 + (139 - 6) * t);     // 6 (cyan) → 139 (violet)
  const g = Math.round(182 + (92 - 182) * t);  // 182 → 92
  const b = Math.round(212 + (246 - 212) * t); // 212 → 246
  return {
    background: `rgba(${r}, ${g}, ${b}, ${0.18 + 0.42 * t})`,
    color: "var(--text)",
  };
}

export function JaccardHeatmap({ symbols, matrix }: Props) {
  const n = symbols.length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        role="table"
        aria-label="Jaccard holdings overlap heatmap"
        style={{
          display: "grid",
          gridTemplateColumns: `auto repeat(${n}, 1fr)`,
          gap: 2,
          fontSize: 12,
        }}
      >
        {/* Header row: blank corner + column labels */}
        <span />
        {symbols.map((s) => (
          <span
            key={`colh-${s}`}
            className="mono"
            style={{
              fontSize: 10,
              color: "var(--muted)",
              textAlign: "center",
              padding: "4px 2px",
              letterSpacing: "0.04em",
            }}
          >
            {s}
          </span>
        ))}

        {/* Data rows */}
        {symbols.map((rowSym, i) => (
          <Fragment key={`row-${rowSym}`}>
            <span
              className="mono"
              style={{
                fontSize: 10,
                color: "var(--muted)",
                textAlign: "right",
                padding: "4px 8px 4px 0",
                alignSelf: "center",
                letterSpacing: "0.04em",
              }}
            >
              {rowSym}
            </span>
            {symbols.map((colSym, j) => {
              const v = matrix[i]?.[j] ?? 0;
              const isDiagonal = i === j;
              return (
                <div
                  key={`cell-${i}-${j}`}
                  role="cell"
                  data-row={i}
                  data-col={j}
                  data-diagonal={isDiagonal ? "true" : undefined}
                  aria-label={`${rowSym} × ${colSym}: ${v.toFixed(2)}`}
                  className="mono"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "10px 4px",
                    borderRadius: 4,
                    fontSize: 12,
                    minHeight: 36,
                    ...cellStyle(v, isDiagonal),
                  }}
                >
                  {v.toFixed(2)}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--muted)" }}>
        <span>Low overlap</span>
        <span>High overlap</span>
      </div>
      <div
        aria-hidden
        style={{
          height: 4,
          borderRadius: 2,
          background: "linear-gradient(to right, var(--cyan), var(--violet))",
        }}
      />
    </div>
  );
}
