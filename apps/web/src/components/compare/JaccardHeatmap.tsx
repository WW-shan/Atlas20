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
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <table
        aria-label="Jaccard holdings overlap heatmap"
        style={{
          width: "100%",
          minWidth: 0,
          borderCollapse: "separate",
          borderSpacing: 2,
          fontSize: 12,
        }}
      >
        <thead>
          <tr>
            <th
              scope="col"
              style={{
                borderBottom: "none",
                padding: "4px 8px",
                fontSize: 10,
                color: "var(--muted)",
                textAlign: "right",
                letterSpacing: "0.04em",
              }}
            >
              Strategy
            </th>
            {symbols.map((s) => (
              <th
                key={`colh-${s}`}
                scope="col"
                className="mono"
                style={{
                  borderBottom: "none",
                  fontSize: 10,
                  color: "var(--muted)",
                  textAlign: "center",
                  padding: "4px 2px",
                  letterSpacing: "0.04em",
                }}
              >
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((rowSym, i) => (
            <tr key={`row-${rowSym}`}>
              <th
                scope="row"
                className="mono"
                style={{
                  borderBottom: "none",
                  fontSize: 10,
                  color: "var(--muted)",
                  textAlign: "right",
                  padding: "4px 8px 4px 0",
                  letterSpacing: "0.04em",
                  verticalAlign: "middle",
                }}
              >
                {rowSym}
              </th>
              {symbols.map((colSym, j) => {
                const v = matrix[i]?.[j] ?? 0;
                const isDiagonal = i === j;
                return (
                  <td
                    key={`cell-${i}-${j}`}
                    data-row={i}
                    data-col={j}
                    data-diagonal={isDiagonal ? "true" : undefined}
                    aria-label={`${rowSym} × ${colSym}: ${v.toFixed(2)}`}
                    className="mono"
                    style={{
                      borderBottom: "none",
                      textAlign: "center",
                      verticalAlign: "middle",
                      padding: "10px 4px",
                      borderRadius: 4,
                      fontSize: 12,
                      height: 36,
                      ...cellStyle(v, isDiagonal),
                    }}
                  >
                    {v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

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
