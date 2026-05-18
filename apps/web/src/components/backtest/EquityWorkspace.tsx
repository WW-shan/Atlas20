import type { RunDetailPayload } from "../../lib/api";
import { OverlayLineChart } from "../charts/OverlayLineChart";
import { KpiTile } from "../ui/KpiTile";

type Props = {
  detail: RunDetailPayload;
};

const TABS = ["Equity", "Drawdown", "Returns", "Turnover", "Trades"] as const;

function formatPct(v: number, digits = 2): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(digits)}%`;
}

export function EquityWorkspace({ detail }: Props) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-card)",
          padding: 20,
        }}
      >
        <div role="tablist" aria-label="Workspace views" style={{ display: "flex", gap: 24, borderBottom: "1px solid var(--border)", marginBottom: 16 }}>
          {TABS.map((t) => (
            <span
              key={t}
              role="tab"
              aria-selected={t === "Equity"}
              aria-disabled={t !== "Equity"}
              tabIndex={t === "Equity" ? 0 : -1}
              style={{
                padding: "8px 0",
                fontSize: 13,
                fontWeight: t === "Equity" ? 600 : 400,
                color: t === "Equity" ? "var(--gold)" : "var(--muted)",
                borderBottom: t === "Equity" ? "2px solid var(--gold)" : "2px solid transparent",
                marginBottom: -1,
                opacity: t === "Equity" ? 1 : 0.5,
              }}
            >
              {t}
            </span>
          ))}
        </div>

        <OverlayLineChart
          series={detail.equity_overlay.series.map((p) => ({ ts: p.ts, values: { atlas: p.atlas, btc: p.btc } }))}
          lines={[
            { id: "atlas", label: "ATLAS", tone: "gold", glow: true },
            { id: "btc",   label: "BTC Benchmark", tone: "violet" },
          ]}
          range="ALL"
          yFormat="percent"
          height={300}
          ariaLabel={`Run ${detail.run_id} equity curve`}
        />
      </div>

      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-card)",
          padding: "16px 20px",
          display: "grid",
          gridTemplateColumns: "repeat(6, 1fr)",
          gap: 20,
        }}
        aria-label="KPI ribbon"
      >
        <KpiTile inline label="CAGR" value={formatPct(detail.kpi.cagr)} />
        <KpiTile inline label="Sharpe" value={detail.kpi.sharpe.toFixed(2)} />
        <KpiTile inline label="Sortino" value={detail.kpi.sortino.toFixed(2)} />
        <KpiTile inline label="Max DD" value={formatPct(detail.kpi.max_dd)} delta={{ value: "", tone: "rose" }} />
        <KpiTile inline label="Calmar" value={detail.kpi.calmar.toFixed(2)} />
        <KpiTile inline label="Win Rate" value={formatPct(detail.kpi.win_rate, 1)} />
      </div>
    </div>
  );
}
