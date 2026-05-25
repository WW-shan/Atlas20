import { useState } from "react";

import type { RunDetailPayload, RunDetailSeriesPoint, RunTradeRow, RunTurnoverRow } from "../../lib/api";
import { OverlayLineChart } from "../charts/OverlayLineChart";
import { Pill } from "../ui/Pill";
import { KpiTile } from "../ui/KpiTile";

type Props = {
  detail: RunDetailPayload;
};

const TABS = ["Equity", "Drawdown", "Returns", "Turnover", "Trades"] as const;
type WorkspaceTab = (typeof TABS)[number];

function formatPct(v: number, digits = 2): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(digits)}%`;
}

function formatPlainPct(v: number | null | undefined, digits = 1): string {
  return typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(digits)}%` : "--";
}

function formatNumber(v: number | null | undefined, digits = 2): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "--";
}

function statusTone(status: RunDetailPayload["status"]): "cyan" | "emerald" | "rose" | "muted" {
  switch (status) {
    case "running":
      return "cyan";
    case "completed":
      return "emerald";
    case "failed":
    case "cancelled":
      return "rose";
    case "queued":
      return "muted";
  }
}

function statusLabel(status: RunDetailPayload["status"]): string {
  switch (status) {
    case "running":
      return "RUNNING";
    case "completed":
      return "COMPLETED";
    case "failed":
      return "FAILED";
    case "cancelled":
      return "CANCELLED";
    case "queued":
      return "QUEUED";
  }
}

function outputMessage(detail: RunDetailPayload): string {
  if (detail.status === "queued" || detail.status === "running") {
    return "Waiting for backend output";
  }
  if (detail.equity_overlay.series.length === 0) {
    return "Completed without a backend curve";
  }
  return "Loaded from backend output";
}

function toChartSeries(series: RunDetailSeriesPoint[]) {
  return series.map((p) => ({ ts: p.ts, values: { atlas: p.atlas, btc: p.btc } }));
}

function chartSeries(detail: RunDetailPayload, tab: WorkspaceTab): RunDetailSeriesPoint[] {
  switch (tab) {
    case "Drawdown":
      return detail.drawdown_series ?? [];
    case "Returns":
      return detail.return_series ?? [];
    case "Equity":
      return detail.equity_overlay.series;
    case "Turnover":
    case "Trades":
      return [];
  }
}

function EmptyPanel({ label }: { label: string }) {
  return (
    <div
      style={{
        flex: 1,
        minHeight: 220,
        display: "grid",
        placeItems: "center",
        color: "var(--muted)",
        fontFamily: "var(--font-mono)",
        fontSize: 12,
      }}
    >
      {label}
    </div>
  );
}

function ChartPanel({ detail, tab }: { detail: RunDetailPayload; tab: Extract<WorkspaceTab, "Equity" | "Drawdown" | "Returns"> }) {
  const series = chartSeries(detail, tab);
  const label = tab === "Equity" ? "equity curve" : tab === "Drawdown" ? "drawdown curve" : "daily return curve";
  return (
    <div role="tabpanel" aria-label={`${tab} view`} style={{ flex: 1, minHeight: 0, display: "flex" }}>
      <OverlayLineChart
        series={toChartSeries(series)}
        lines={[
          { id: "atlas", label: "ATLAS", tone: "gold", glow: true },
          { id: "btc", label: "BTC Benchmark", tone: "violet" },
        ]}
        range="ALL"
        yFormat="percent"
        height={300}
        fillContainer
        ariaLabel={`Run ${detail.run_id} ${label}`}
      />
    </div>
  );
}

function TurnoverTable({ rows }: { rows: RunTurnoverRow[] }) {
  if (rows.length === 0) {
    return <EmptyPanel label="No turnover rows for this run" />;
  }
  return (
    <div role="tabpanel" aria-label="Turnover view" style={{ flex: 1, overflow: "auto" }}>
      <table aria-label="Turnover rows" style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ color: "var(--muted)", textAlign: "left" }}>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Strategy</th>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Annualized Turnover</th>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Avg Rebalance</th>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Avg Holdings</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 30).map((row, index) => (
            <tr key={`${row.strategy}-${index}`}>
              <td style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>{row.strategy}</td>
              <td className="mono" style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>
                {formatPlainPct(row.annualized_turnover)}
              </td>
              <td className="mono" style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>
                {formatPlainPct(row.avg_turnover_per_rebalance)}
              </td>
              <td className="mono" style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>
                {formatNumber(row.average_holdings, 1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TradesTable({ rows }: { rows: RunTradeRow[] }) {
  if (rows.length === 0) {
    return <EmptyPanel label="No trade rows for this run" />;
  }
  return (
    <div role="tabpanel" aria-label="Trades view" style={{ flex: 1, overflow: "auto" }}>
      <table aria-label="Trade rows" style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ color: "var(--muted)", textAlign: "left" }}>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Date</th>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Coin</th>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Rank</th>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Score</th>
            <th style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)" }}>Weight</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 50).map((row, index) => (
            <tr key={`${row.rebalance_date}-${row.coin_id}-${index}`}>
              <td className="mono" style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>
                {row.rebalance_date}
              </td>
              <td style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>{row.coin_id}</td>
              <td className="mono" style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>
                {row.coin_rank ?? "--"}
              </td>
              <td className="mono" style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>
                {formatNumber(row.coin_score, 2)}
              </td>
              <td className="mono" style={{ padding: "9px 10px", borderBottom: "1px solid var(--border)" }}>
                {formatPlainPct(row.coin_weight)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EquityWorkspace({ detail }: Props) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("Equity");

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
      <div
        style={{
          flex: 1,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-card)",
          padding: 20,
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        <div role="tablist" aria-label="Workspace views" style={{ display: "flex", gap: 24, borderBottom: "1px solid var(--border)", marginBottom: 16 }}>
          {TABS.map((t) => {
            const active = t === activeTab;
            return (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setActiveTab(t)}
                style={{
                  padding: "8px 0",
                  fontSize: 13,
                  fontWeight: active ? 600 : 400,
                  color: active ? "var(--text)" : "var(--muted)",
                  borderBottom: active ? "2px solid var(--violet)" : "2px solid transparent",
                  marginBottom: -1,
                  opacity: active ? 1 : 0.75,
                  background: "transparent",
                  cursor: active ? "default" : "pointer",
                }}
              >
                {t}
              </button>
            );
          })}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 12px",
            marginBottom: 16,
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-input)",
          }}
          aria-label="Run detail status"
        >
          <Pill tone={statusTone(detail.status)} size="xs" live>
            {statusLabel(detail.status)}
          </Pill>
          <span className="mono" style={{ fontSize: 12 }}>{detail.run_id}</span>
          <span className="muted" style={{ fontSize: 12 }}>{outputMessage(detail)}</span>
          {detail.selected_strategy ? (
            <span className="muted" style={{ fontSize: 12, marginLeft: "auto", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {detail.selected_strategy}
            </span>
          ) : null}
        </div>

        {activeTab === "Equity" ? <ChartPanel detail={detail} tab="Equity" /> : null}
        {activeTab === "Drawdown" ? <ChartPanel detail={detail} tab="Drawdown" /> : null}
        {activeTab === "Returns" ? <ChartPanel detail={detail} tab="Returns" /> : null}
        {activeTab === "Turnover" ? <TurnoverTable rows={detail.turnover_rows ?? []} /> : null}
        {activeTab === "Trades" ? <TradesTable rows={detail.trade_rows ?? []} /> : null}
      </div>

      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-card)",
          padding: "16px 20px",
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 20,
          flexShrink: 0,
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
