import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card } from "../../components/ui/Card";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { OverlayLineChart } from "../../components/charts/OverlayLineChart";
import { StrategyChip, AddStrategyChip } from "../../components/compare/StrategyChip";
import { ComparisonTable } from "../../components/compare/ComparisonTable";
import { JaccardHeatmap } from "../../components/compare/JaccardHeatmap";
import { SharedHoldingsBars } from "../../components/compare/SharedHoldingsBars";

import { fallbackCompare, getCompare } from "../../lib/api";
import type { CompareSelectionItem } from "../../lib/api";
import type { ChartRange } from "../../components/ui/types";
import { qk } from "../../lib/qk";

const DEFAULT_SELECTIONS: CompareSelectionItem[] = [
  { id: "atlas",    label: "ATLAS Adaptive v3", tone: "gold" },
  { id: "momentum", label: "Momentum Family",   tone: "violet" },
  { id: "meanrev",  label: "Mean Reversion",    tone: "cyan" },
];

const RANGES: ChartRange[] = ["1M", "3M", "YTD", "1Y", "ALL"];

const lineToneFor = (tone: CompareSelectionItem["tone"]) => tone;

export function StrategyCompareTab() {
  const [selections] = useState<CompareSelectionItem[]>(DEFAULT_SELECTIONS);
  const [range, setRange] = useState<ChartRange>("YTD");
  const ids = useMemo(() => selections.map((s) => s.id), [selections]);

  const apiEnabled = import.meta.env.MODE !== "test";
  const query = useQuery({
    queryKey: qk.compare(ids, range),
    queryFn: () => getCompare(ids, range),
    initialData: fallbackCompare,
    enabled: apiEnabled,
  });

  const data = query.data ?? fallbackCompare;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, padding: 24 }}>
      {/* ===== Chip cluster ===== */}
      <Card ariaLabel="Strategy selection">
        <div role="list" aria-label="Selected strategies" style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          {selections.map((s) => (
            <StrategyChip key={s.id} item={s} />
          ))}
          <AddStrategyChip />
          <span className="muted" style={{ marginLeft: "auto", fontSize: 12 }}>
            <span className="mono">{selections.length}</span> selected
          </span>
        </div>
      </Card>

      {/* ===== Equity overlay ===== */}
      <Card ariaLabel="Strategy equity overlay">
        <SectionHeader
          rightSlot={
            <div role="tablist" aria-label="Equity overlay range" style={{ display: "flex", gap: 4 }}>
              {RANGES.map((r) => {
                const active = r === range;
                return (
                  <button
                    key={r}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setRange(r)}
                    className="mono"
                    style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      color: active ? "var(--text)" : "var(--muted)",
                      borderBottom: active ? "2px solid var(--violet)" : "2px solid transparent",
                      background: "transparent",
                      cursor: "pointer",
                    }}
                  >
                    {r}
                  </button>
                );
              })}
            </div>
          }
        >
          {`EQUITY OVERLAY · ${range}`}
        </SectionHeader>

        <OverlayLineChart
          series={data.equity.map((p) => ({ ts: p.ts, values: p.values }))}
          lines={selections.map((s) => ({
            id: s.id,
            label: s.label,
            tone: lineToneFor(s.tone),
            glow: s.tone === "gold",
          }))}
          range={range}
          yFormat="percent"
          height={280}
          ariaLabel={`Equity overlay across ${selections.length} strategies, range ${range}`}
        />

        <div style={{ display: "flex", gap: 24, marginTop: 12, fontSize: 12, flexWrap: "wrap" }}>
          {selections.map((s) => (
            <span key={s.id} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span
                aria-hidden
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: `var(--${s.tone})`,
                  display: "inline-block",
                }}
              />
              <span>{s.label}</span>
            </span>
          ))}
        </div>
      </Card>

      {/* ===== Metrics 60% + Overlap 40% ===== */}
      <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 24 }}>
        <Card ariaLabel="Metric comparison">
          <SectionHeader>METRIC COMPARISON</SectionHeader>
          <ComparisonTable selections={selections} metrics={data.metrics} />
          <div style={{ marginTop: 12, fontSize: 11, color: "var(--muted)" }}>
            <span
              className="mono"
              aria-label="Best per row legend"
              style={{
                display: "inline-block",
                padding: "1px 8px",
                background: "rgba(245,158,11,0.06)",
                color: "var(--gold)",
                border: "1px solid rgba(245,158,11,0.30)",
                borderRadius: 4,
                fontSize: 10,
                letterSpacing: "0.08em",
              }}
            >
              BEST
            </span>{" "}
            <span style={{ marginLeft: 8 }}>highlighted per row · direction-aware</span>
          </div>
        </Card>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <Card ariaLabel="Holdings overlap heatmap">
            <SectionHeader>HOLDINGS OVERLAP · JACCARD</SectionHeader>
            <JaccardHeatmap
              symbols={data.overlap.symbols}
              matrix={data.overlap.matrix}
            />
          </Card>
          <Card ariaLabel="Top shared holdings">
            <SectionHeader>TOP SHARED HOLDINGS</SectionHeader>
            <SharedHoldingsBars holdings={data.overlap.sharedHoldings} />
          </Card>
        </div>
      </div>
    </div>
  );
}
