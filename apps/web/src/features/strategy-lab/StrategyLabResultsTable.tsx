import type { CSSProperties } from "react";

import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { SectionHeader } from "../../components/ui/SectionHeader";
import type { StrategyLabResult } from "../../lib/api";

export type StrategyLabSortMetric = "sharpe" | "return_pct" | "calmar" | "max_dd";

type Props = {
  results: StrategyLabResult[];
  sortMetric: StrategyLabSortMetric;
  onSortMetricChange: (metric: StrategyLabSortMetric) => void;
  onOpenRun: (runId: string) => void;
};

const metricLabels: Record<StrategyLabSortMetric, string> = {
  sharpe: "Sharpe",
  return_pct: "CAGR",
  calmar: "Calmar",
  max_dd: "Max DD",
};

export function StrategyLabResultsTable({ results, sortMetric, onSortMetricChange, onOpenRun }: Props) {
  const sorted = sortedResults(results, sortMetric);

  return (
    <Card ariaLabel="Strategy Lab ranked results">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <SectionHeader>Ranked results</SectionHeader>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--muted)" }}>
          Sort
          <select
            value={sortMetric}
            onChange={(event) => onSortMetricChange(event.target.value as StrategyLabSortMetric)}
            aria-label="Sort Strategy Lab results"
            style={{
              background: "var(--surface)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-input)",
              padding: "6px 8px",
            }}
          >
            {Object.entries(metricLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
      </div>

      {sorted.length === 0 ? (
        <EmptyState title="No completed results yet" />
      ) : (
        <div style={{ overflowX: "auto", marginTop: 12 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ color: "var(--muted)", textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                <th style={cellStyle}>Run</th>
                <th style={cellStyle}>Preset</th>
                <th style={cellStyle}>Top N</th>
                <th style={cellStyle}>Rebalance</th>
                <th style={cellStyle}>CAGR</th>
                <th style={cellStyle}>Sharpe</th>
                <th style={cellStyle}>Calmar</th>
                <th style={cellStyle}>Max DD</th>
                <th style={cellStyle} />
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr key={row.run_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={cellStyle} className="mono">{row.run_id}</td>
                  <td style={cellStyle}>{row.preset}</td>
                  <td style={cellStyle} className="mono">{row.topN}</td>
                  <td style={cellStyle}>{row.rebalance}</td>
                  <td style={cellStyle} className="mono">{formatPct(row.return_pct)}</td>
                  <td style={cellStyle} className="mono">{formatNumber(row.sharpe)}</td>
                  <td style={cellStyle} className="mono">{formatNumber(row.calmar)}</td>
                  <td style={cellStyle} className="mono">{formatPct(row.max_dd)}</td>
                  <td style={{ ...cellStyle, textAlign: "right" }}>
                    <Button variant="outline-muted" onClick={() => onOpenRun(row.run_id)}>
                      Open {row.run_id}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function sortedResults(results: StrategyLabResult[], sort: StrategyLabSortMetric): StrategyLabResult[] {
  return [...results].sort((a, b) => {
    const av = metricValue(a, sort);
    const bv = metricValue(b, sort);
    return bv - av;
  });
}

function metricValue(row: StrategyLabResult, sort: StrategyLabSortMetric): number {
  return row[sort] ?? Number.NEGATIVE_INFINITY;
}

function formatPct(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(2);
}

const cellStyle: CSSProperties = {
  padding: "10px 8px",
  whiteSpace: "nowrap",
};
