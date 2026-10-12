import { useQuery } from "@tanstack/react-query";

import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { Pill } from "../../components/ui/Pill";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { Skeleton } from "../../components/ui/Skeleton";
import { getLiveResearch, type LiveJournalRow, type LiveWeight } from "../../lib/api";

 type LiveResearchPayload = Awaited<ReturnType<typeof getLiveResearch>>;
type LiveSpot = NonNullable<LiveResearchPayload["spot"]>;
type LiveOos = NonNullable<LiveResearchPayload["oos"]>;
type LiveDerivatives = NonNullable<LiveResearchPayload["derivatives"]>;import { qk } from "../../lib/qk";

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 12,
} as const;

const thStyle = {
  textAlign: "left",
  padding: "8px 10px",
  borderBottom: "1px solid var(--border)",
  color: "var(--muted)",
  fontSize: 10,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
} as const;

const tdStyle = {
  padding: "9px 10px",
  borderBottom: "1px solid var(--border)",
} as const;

export function LiveResearchTab() {
  const live = useQuery({
    queryKey: qk.liveResearch(),
    queryFn: getLiveResearch,
  });

  if (live.isLoading && live.data === undefined) {
    return (
      <div style={{ padding: 24, display: "grid", gap: 16 }}>
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} variant="card" height={index === 0 ? "280px" : "180px"} />
        ))}
      </div>
    );
  }

  if (live.isError && live.data === undefined) {
    return (
      <div style={{ padding: 24 }}>
        <ErrorBanner
          message="Unable to load live research."
          onRetry={() => { void live.refetch(); }}
        />
      </div>
    );
  }

  const data = live.data;
  if (!data) return null;
  const unavailableArtifacts = data.artifacts.filter((artifact) => !artifact.available);
  const hasData = data.spot !== null || data.oos !== null || data.derivatives !== null;

  return (
    <div className="live-research-tab" style={{ padding: 24, display: "grid", gap: 16 }}>
      <Card ariaLabel="Spot research">
        <SectionHeader
          rightSlot={
            <Button
              variant="outline-violet"
              size="sm"
              loading={live.isFetching}
              onClick={() => { void live.refetch(); }}
            >
              REFRESH LIVE DATA
            </Button>
          }
        >
          SPOT RESEARCH
        </SectionHeader>
        {data.spot ? (
          <SpotResearch spot={data.spot} />
        ) : (
          <EmptyState title="Spot research signal unavailable" sub="The latest signal artifact is missing or unreadable." />
        )}
      </Card>

      {data.oos ? (
        <Card ariaLabel="Out-of-sample tracking">
          <SectionHeader>OUT-OF-SAMPLE TRACKING</SectionHeader>
          <OosTracking oos={data.oos} />
        </Card>
      ) : null}

      {data.derivatives ? (
        <Card ariaLabel="Derivatives live monitor">
          <SectionHeader>DERIVATIVES LIVE MONITOR</SectionHeader>
          <DerivativesMonitor derivatives={data.derivatives} />
        </Card>
      ) : null}

      {data.derivatives?.journal?.length ? (
        <Card ariaLabel="Execution journal">
          <SectionHeader>EXECUTION JOURNAL</SectionHeader>
          <JournalTable rows={data.derivatives.journal} />
        </Card>
      ) : null}

      {!hasData ? (
        <EmptyState title="Live research artifacts unavailable" sub="No current research or live-operation section could be loaded." />
      ) : null}

      {unavailableArtifacts.length > 0 ? (
        <Card ariaLabel="Artifact availability">
          <SectionHeader>ARTIFACT AVAILABILITY</SectionHeader>
          <div role="list" aria-label="Unavailable live research artifacts" style={{ display: "grid", gap: 8 }}>
            {unavailableArtifacts.map((artifact) => (
              <span
                key={artifact.id}
                role="listitem"
                className="mono muted"
                style={{ fontSize: 12 }}
              >
                {artifact.id} · {artifact.path} · unavailable
              </span>
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function SpotResearch({ spot }: { spot: LiveSpot }) {
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
        <Pill tone={spot.status === "validated" ? "emerald" : "gold-outline"} size="xs">
          {spot.status}
        </Pill>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700 }}>{spot.trial_id}</span>
        {spot.signal_date && <span className="muted mono" style={{ fontSize: 12 }}>{spot.signal_date}</span>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        <Metric label="Target gross" value={formatPct(spot.gross_exposure)} />
        <Metric label="Current gross" value={formatPct(spot.current_gross_exposure)} />
        <Metric label="BTC gate" value={spot.btc_gate_open ? "OPEN" : "CLOSED"} />
        <Metric label="Trade required" value={spot.trade_required ? "YES" : "NO"} />
        <Metric label="Cost basis" value={`${spot.cost_bps?.toFixed(0) ?? "—"} bps`} />
        <Metric label="Panel date" value={spot.panel_last_date ?? "—"} />
      </div>

      <div style={{ minWidth: 0 }}>
        <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
          Current target weights
        </div>
        <div style={{ overflowX: "auto", minWidth: 0 }}>
          <table aria-label="Current spot target weights" style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Asset</th>
              <th style={thStyle}>Target</th>
              <th style={thStyle}>Current</th>
            </tr>
          </thead>
          <tbody>
            {(spot.weights ?? []).map((weight) => <WeightRow key={weight.asset} weight={weight} />)}
          </tbody>
          </table>
        </div>
      </div>

      {spot.frozen?.length ? (
        <div style={{ minWidth: 0 }}>
          <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            Frozen evaluation
          </div>
          <div style={{ overflowX: "auto", minWidth: 0 }}>
            <table aria-label="Frozen evaluation metrics" style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Fill</th>
                <th style={thStyle}>Multiple</th>
                <th style={thStyle}>Sharpe</th>
                <th style={thStyle}>Max DD</th>
                <th style={thStyle}>DSR</th>
              </tr>
            </thead>
            <tbody>
              {spot.frozen.map((row, index) => (
                <tr key={`${row.trial_id}-${row.fill_hours}-${row.fill_policy}-${index}`}>
                  <td style={tdStyle} className="mono">{row.fill_policy ?? "—"}</td>
                  <td style={tdStyle} className="mono">{formatMultiplier(row.multiple)}</td>
                  <td style={tdStyle} className="mono">{formatNumber(row.sharpe)}</td>
                  <td style={tdStyle} className="mono">{formatPct(row.max_drawdown)}</td>
                  <td style={tdStyle} className="mono">{formatNumber(row.deflated_sharpe_probability)}</td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <span className="muted" style={{ fontSize: 11 }}>{spot.rule}</span>
    </div>
  );
}

function WeightRow({ weight }: { weight: LiveWeight }) {
  return (
    <tr>
      <td style={tdStyle} className="mono">{weight.asset.toUpperCase()}</td>
      <td style={tdStyle} className="mono">{formatPct(weight.target)}</td>
      <td style={tdStyle} className="mono">{formatPct(weight.current)}</td>
    </tr>
  );
}

function OosTracking({ oos }: { oos: LiveOos }) {
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        <Metric label="Window" value={`${oos.days} days`} />
        <Metric label="H5" value={formatMultiplier(oos.multiple)} />
        <Metric label="BTC" value={formatMultiplier(oos.benchmark_multiple)} />
        <Metric label="H5 − BTC" value={formatSignedPct(oos.multiple - oos.benchmark_multiple)} />
        <Metric label="Max DD" value={formatPct(oos.max_drawdown)} />
      </div>

      {oos.stress?.length ? (
        <div style={{ overflowX: "auto", minWidth: 0 }}>
          <table aria-label="Out-of-sample cost stress" style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Cost</th>
              <th style={thStyle}>Multiple</th>
              <th style={thStyle}>Max DD</th>
            </tr>
          </thead>
          <tbody>
            {oos.stress.map((row) => (
              <tr key={`${row.fill_policy}-${row.cost_bps}`}>
                <td style={tdStyle} className="mono">{row.cost_bps?.toFixed(0) ?? "—"} bps</td>
                <td style={tdStyle} className="mono">{formatMultiplier(row.multiple)}</td>
                <td style={tdStyle} className="mono">{formatPct(row.max_drawdown)}</td>
              </tr>
            ))}
          </tbody>
          </table>
        </div>
      ) : null}

      <span className="muted" style={{ fontSize: 11 }}>
        Short-window tracking; not a validation claim. The strategy remains provisional until every robustness gate is passed.
      </span>
    </div>
  );
}

function DerivativesMonitor({ derivatives }: { derivatives: LiveDerivatives }) {
  const health = derivatives.health;
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
        <Pill tone={health.status === "healthy" ? "emerald" : "rose"} size="xs">{health.status}</Pill>
        <span className="mono muted" style={{ fontSize: 12 }}>{health.spec ?? "—"}</span>
        <span className="mono muted" style={{ fontSize: 12 }}>{health.checked_at ?? "—"}</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        <Metric label="Equity" value={`${health.equity?.toFixed(2) ?? "—"} USDT equity`} />
        <Metric label="Gross" value={`${health.position_value?.toFixed(2) ?? "—"} USDT gross notional`} />
        <Metric label="Hard failures" value={`${health.hard_failures} hard failures`} />
        <Metric label="Signal date" value={health.signal_date ?? "—"} />
      </div>

      <div role="list" aria-label="Derivatives audit checks" style={{ display: "grid", gap: 8 }}>
        {(health.checks ?? []).map((check, index) => (
          <div
            key={`${check.check}-${index}`}
            role="listitem"
            style={{
              display: "grid",
              gridTemplateColumns: "16px 1fr",
              gap: 10,
              alignItems: "start",
              fontSize: 12,
            }}
          >
            <span style={{ color: check.ok ? "var(--emerald)" : "var(--rose)" }}>{check.ok ? "✓" : "✕"}</span>
            <span>
              <span>{check.check}</span>
              <span className="muted" style={{ display: "block", fontSize: 11 }}>{check.detail}</span>
            </span>
          </div>
        ))}
      </div>

      <Pill tone={derivatives.equivalence.passed ? "emerald" : "rose"} size="xs">
        {derivatives.equivalence.passed ? "Signal equivalence passed" : "Signal equivalence failed"}
      </Pill>
    </div>
  );
}

function JournalTable({ rows }: { rows: LiveJournalRow[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table aria-label="Derivatives execution journal" style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Date</th>
            <th style={thStyle}>Signal</th>
            <th style={thStyle}>Equity</th>
            <th style={thStyle}>Gross</th>
            <th style={thStyle}>uPnL</th>
            <th style={thStyle}>Positions</th>
            <th style={thStyle}>Trades</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.date}-${index}`}>
              <td style={tdStyle} className="mono">{row.date ?? "—"}</td>
              <td style={tdStyle} className="mono">{row.signal_date ?? "—"}</td>
              <td style={tdStyle} className="mono">{row.equity?.toFixed(6) ?? "—"}</td>
              <td style={tdStyle} className="mono">{row.position_value?.toFixed(3) ?? "—"}</td>
              <td style={tdStyle} className="mono">{row.unrealised_pnl?.toFixed(4) ?? "—"}</td>
              <td style={tdStyle} className="mono">{row.positions ?? "—"} positions</td>
              <td style={tdStyle} className="mono">{row.trades ?? "—"} trades</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gap: 4 }}>
      <span className="muted" style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
      <span className="mono" style={{ fontSize: 15, fontWeight: 700 }}>{value}</span>
    </div>
  );
}

function formatPct(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function formatSignedPct(value: number | null | undefined): string {
  return value == null ? "—" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function formatMultiplier(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(2);
}
