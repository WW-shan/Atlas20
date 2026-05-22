import type { OverviewPayload } from "../../lib/api";
import type { ConsoleTab } from "../../components/navigation/TabSwitcher";
import { Card } from "../../components/ui/Card";
import { Pill } from "../../components/ui/Pill";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { Button } from "../../components/ui/Button";
import { SparklineChart } from "../../components/charts/SparklineChart";
import { OverlayLineChart } from "../../components/charts/OverlayLineChart";
import { StrategyBarRow } from "../../components/overview/StrategyBarRow";
import { RegimeGauge } from "../../components/overview/RegimeGauge";

type Props = {
  overview: OverviewPayload;
  onNavigate: (tab: ConsoleTab, prefillRunId?: string) => void;
};

function HeroKpi(props: { label: string; value: string; valueColor?: string; valueSize?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }} role="group" aria-label={props.label}>
      <span
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--muted)",
        }}
      >
        {props.label}
      </span>
      <span
        className="mono"
        style={{
          fontSize: props.valueSize ?? 24,
          lineHeight: 1,
          color: props.valueColor,
        }}
      >
        {props.value}
      </span>
    </div>
  );
}

function formatPct(v: number, digits = 2): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(digits)}%`;
}

function formatPctAbs(v: number, digits = 2): string {
  return `${(v * 100).toFixed(digits)}%`;
}

function formatCompactCurrency(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function formatRelativeAge(s: number): string {
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function OverviewTab({ overview, onNavigate }: Props) {
  const { champion, hero_kpi, aum, strategies, regime, rebalance, equity_overlay } = overview;
  const maxBreakdown = Math.max(...strategies.breakdown.map((b) => b.count));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, padding: 24 }}>

      {/* ===== Hero ===== */}
      <Card variant="hero" ariaLabel="Current champion summary">
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 24, alignItems: "center" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <Pill tone="gold-outline" size="xs">CURRENT CHAMPION</Pill>
            <h2 style={{ margin: 0, fontSize: 28, fontWeight: 600, letterSpacing: "-0.01em" }}>
              {champion.display_name}
            </h2>
            <span className="muted" style={{ fontSize: 13 }}>
              {champion.window_start} → <span className="mono">{champion.window_end}</span>
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, auto)", gap: 32, alignItems: "end" }}>
            <HeroKpi label="YTD Return" value={formatPct(hero_kpi.ytdReturn)} valueColor="var(--gold)" valueSize={32} />
            <HeroKpi label="Sharpe" value={hero_kpi.sharpe.toFixed(2)} valueSize={24} />
            <HeroKpi label="Max DD" value={formatPctAbs(hero_kpi.maxDd)} valueColor="var(--rose)" valueSize={24} />
            <HeroKpi label="Win Rate" value={formatPctAbs(hero_kpi.winRate, 1)} valueSize={24} />
          </div>
        </div>
      </Card>

      {/* ===== KPI Triplet ===== */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 24 }}>

        {/* Tracked notional (research, not real AUM) */}
        <Card ariaLabel="Champion equity trend (research)">
          <SectionHeader>TRACKED NOTIONAL · RESEARCH</SectionHeader>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <span className="mono" style={{ fontSize: 28 }}>{formatCompactCurrency(aum.current)}</span>
            <SparklineChart points={aum.sparkline} tone="violet" height={36} width={280} ariaLabel="Champion equity trend (14 samples)" />
            <span className="mono" style={{ fontSize: 12, color: "var(--emerald)" }}>
              {formatPct(aum.deltaPct, 1)} over last 14 data points
            </span>
          </div>
        </Card>

        {/* Active Strategies */}
        <Card ariaLabel="Active strategies breakdown">
          <SectionHeader>ACTIVE STRATEGIES</SectionHeader>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <span className="mono" style={{ fontSize: 28 }}>{strategies.total}</span>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {strategies.breakdown.map((b) => (
                <StrategyBarRow key={b.family} family={b.family} count={b.count} max={maxBreakdown} />
              ))}
            </div>
          </div>
        </Card>

        {/* Market Regime */}
        <Card ariaLabel="Market regime gauge">
          <SectionHeader>MARKET REGIME</SectionHeader>
          <RegimeGauge label={regime.label} score={regime.score} model={regime.model} />
        </Card>
      </div>

      {/* ===== Equity Curve + Latest Rebalance ===== */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24 }}>

        {/* Equity Curve */}
        <Card ariaLabel={`Champion equity curve ${equity_overlay.range}`}>
          <SectionHeader>{`EQUITY CURVE · ${equity_overlay.range}`}</SectionHeader>
          <OverlayLineChart
            series={equity_overlay.series.map((p) => ({ ts: p.ts, values: { atlas: p.atlas, btc: p.btc } }))}
            lines={[
              { id: "atlas", label: equity_overlay.atlas_label, tone: "gold", glow: true },
              { id: "btc",   label: equity_overlay.btc_label,   tone: "violet" },
            ]}
            range={equity_overlay.range}
            yFormat="percent"
            height={280}
            ariaLabel={`${equity_overlay.atlas_label} vs ${equity_overlay.btc_label} equity curve ${equity_overlay.range}`}
          />
          <div style={{ display: "flex", gap: 24, marginTop: 12, fontSize: 12 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--gold)", display: "inline-block" }} />
              <span>{equity_overlay.atlas_label}</span>
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--violet)", display: "inline-block" }} />
              <span>{equity_overlay.btc_label}</span>
            </span>
          </div>
        </Card>

        {/* Latest Rebalance */}
        <Card ariaLabel="Latest rebalance swaps">
          <SectionHeader>LATEST REBALANCE</SectionHeader>
          <span className="muted" style={{ fontSize: 12, display: "block", marginBottom: 16 }}>
            <span className="mono">{rebalance.ts}</span> {champion.rebalance_frequency ?? "—"} · {rebalance.swaps.length} swaps
          </span>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {rebalance.swaps.map((s, i) => (
              <div
                key={i}
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto auto auto auto auto auto",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 13,
                }}
              >
                <span className="mono muted" style={{ fontSize: 11 }}>OUT</span>
                <span className="mono" style={{ color: "var(--muted)" }}>{s.out}</span>
                <span className="muted" style={{ textAlign: "center" }}>→</span>
                <span className="mono muted" style={{ fontSize: 11 }}>IN</span>
                <span className="mono">{s.in}</span>
                <span className="mono" style={{ color: s.deltaPct >= 0 ? "var(--emerald)" : "var(--rose)", textAlign: "right", marginLeft: "auto" }}>
                  {formatPct(s.deltaPct, 1)}
                </span>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => onNavigate("history")}
            style={{
              marginTop: 16,
              fontSize: 12,
              color: "var(--muted)",
              background: "transparent",
              padding: 0,
            }}
          >
            View full rebalance →
          </button>
        </Card>
      </div>

      {/* ===== Action Strip ===== */}
      <Card ariaLabel="Quick actions">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", gap: 12 }}>
            <Button variant="gold" onClick={() => onNavigate("backtest")}>▶ RUN NEW BACKTEST</Button>
            <Button variant="outline-violet" onClick={() => onNavigate("compare")}>COMPARE STRATEGIES</Button>
            <Button variant="outline-muted" onClick={() => onNavigate("reports")}>GENERATE REPORT</Button>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            <span className="muted">Last sync:</span>
            <span className="mono">{formatRelativeAge(overview.last_sync_seconds)}</span>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--emerald)", display: "inline-block" }} />
          </div>
        </div>
      </Card>
    </div>
  );
}
