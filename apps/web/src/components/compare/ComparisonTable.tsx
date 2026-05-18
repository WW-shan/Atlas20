import type { CompareMetricKey, CompareSelectionItem, ComparePayload } from "../../lib/api";
import { compareMetricMeta } from "../../lib/api";

type Props = {
  selections: CompareSelectionItem[];
  metrics: ComparePayload["metrics"];
};

const ORDER: CompareMetricKey[] = [
  "cagr",
  "sharpe",
  "sortino",
  "max_dd",
  "calmar",
  "win_rate",
  "avg_turnover",
  "trades_per_year",
];

function formatValue(v: number, format: "percent" | "ratio" | "count"): string {
  if (format === "percent") {
    const sign = v > 0 ? "+" : "";
    return `${sign}${(v * 100).toFixed(2)}%`;
  }
  if (format === "count") return v.toFixed(0);
  return v.toFixed(2);
}

function findBest(
  row: Record<string, number>,
  ids: string[],
  direction: "higher-is-better" | "lower-is-better",
): string | null {
  const present = ids.filter((id) => typeof row[id] === "number");
  if (present.length === 0) return null;
  // "lower-is-better" compares by magnitude so signed metrics (negative
  // drawdowns) and positive metrics (turnover, trade count) share semantics.
  const key = direction === "higher-is-better"
    ? (id: string) => row[id]
    : (id: string) => -Math.abs(row[id]);
  return [...present].sort((a, b) => key(a) - key(b)).pop() ?? null;
}

export function ComparisonTable({ selections, metrics }: Props) {
  const ids = selections.map((s) => s.id);

  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 13,
        }}
        aria-label="Metric comparison table"
      >
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            <th
              scope="col"
              style={{
                textAlign: "left",
                padding: "10px 12px",
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--muted)",
              }}
            >
              METRIC
            </th>
            {selections.map((s) => (
              <th
                key={s.id}
                scope="col"
                style={{
                  textAlign: "right",
                  padding: "10px 12px",
                  fontSize: 11,
                  fontWeight: 600,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                }}
              >
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ORDER.map((key) => {
            const meta = compareMetricMeta[key];
            const row = metrics[key] ?? {};
            const bestId = findBest(row, ids, meta.direction);

            return (
              <tr key={key} style={{ borderBottom: "1px solid var(--border)" }}>
                <th
                  scope="row"
                  style={{
                    textAlign: "left",
                    padding: "10px 12px",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--text)",
                  }}
                >
                  {meta.label}
                </th>
                {selections.map((s) => {
                  const v = row[s.id];
                  const isBest = bestId === s.id;
                  return (
                    <td
                      key={s.id}
                      data-metric={key}
                      data-strategy={s.id}
                      data-best={isBest ? "true" : undefined}
                      className="mono"
                      style={{
                        textAlign: "right",
                        padding: "10px 12px",
                        fontSize: 13,
                        color: isBest ? "var(--gold)" : "var(--text)",
                        background: isBest ? "rgba(245,158,11,0.06)" : "transparent",
                        fontWeight: isBest ? 600 : 400,
                      }}
                    >
                      {typeof v === "number" ? formatValue(v, meta.format) : "—"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
