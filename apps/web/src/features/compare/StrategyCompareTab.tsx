import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card } from "../../components/ui/Card";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { OverlayLineChart } from "../../components/charts/OverlayLineChart";
import { StrategyChip, AddStrategyChip } from "../../components/compare/StrategyChip";
import { ComparisonTable } from "../../components/compare/ComparisonTable";
import { JaccardHeatmap } from "../../components/compare/JaccardHeatmap";
import { SharedHoldingsBars } from "../../components/compare/SharedHoldingsBars";
import { AddStrategyModal } from "./AddStrategyModal";

import { fallbackCompare, fallbackOptions, getCompare, getOptions } from "../../lib/api";
import type { CompareSelectionItem } from "../../lib/api";
import type { ChartRange } from "../../components/ui/types";
import { qk } from "../../lib/qk";

const DEFAULT_SELECTIONS: CompareSelectionItem[] = [
  { id: "atlas",    label: "ATLAS Adaptive v3", tone: "gold" },
  { id: "momentum", label: "Momentum Top-10",   tone: "violet" },
  { id: "meanrev",  label: "Mean Reversion v2", tone: "cyan" },
];

const RANGES: ChartRange[] = ["1M", "3M", "YTD", "1Y", "ALL"];
const TONES: CompareSelectionItem["tone"][] = ["gold", "violet", "cyan", "emerald"];
const PRESET_COMPARE_IDS: Record<string, string> = {
  "ATLAS Adaptive v3": "atlas",
  "Momentum Top-10": "momentum",
  "Mean Reversion v2": "meanrev",
};

const lineToneFor = (tone: CompareSelectionItem["tone"]) => tone;

function resolveCompareId(label: string): string {
  return PRESET_COMPARE_IDS[label] ?? label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

export function StrategyCompareTab() {
  const [selections, setSelections] = useState<CompareSelectionItem[]>(DEFAULT_SELECTIONS);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [range, setRange] = useState<ChartRange>("YTD");
  const ids = useMemo(() => selections.map((s) => s.id), [selections]);
  const selectedLabels = useMemo(() => selections.map((selection) => selection.label), [selections]);

  const options = useQuery({
    queryKey: qk.options(),
    queryFn: getOptions,
    initialData: fallbackOptions,
  });

  const query = useQuery({
    queryKey: qk.compare(ids, range),
    queryFn: () => getCompare(ids, range),
    initialData: fallbackCompare,
    placeholderData: (previous) => previous ?? fallbackCompare,
  });

  const data = query.data ?? fallbackCompare;
  const strategyOptions = useMemo(() => {
    return Array.from(new Set([...selections.map((selection) => selection.label), ...(options.data?.presets ?? [])]));
  }, [options.data?.presets, selections]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    params.set("ids", ids.join(","));
    params.set("range", range);
    const next = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
    window.history.replaceState(null, "", next);
  }, [ids, range]);

  const handleAddStrategies = (labels: string[]) => {
    setSelections((current) => labels.map((label, index) => {
      const id = resolveCompareId(label);
      const existing = current.find((selection) => selection.id === id);
      if (existing) return { ...existing, label };
      return { id, label, tone: TONES[index % TONES.length] };
    }));
    setAddModalOpen(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, padding: 24 }}>
      {/* ===== Chip cluster ===== */}
      <Card ariaLabel="Strategy selection">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <div role="list" aria-label="Selected strategies" style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            {selections.map((s) => (
              <StrategyChip key={s.id} item={s} />
            ))}
          </div>
          <AddStrategyChip onClick={() => setAddModalOpen(true)} />
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

      <AddStrategyModal
        open={addModalOpen}
        strategies={strategyOptions}
        selected={selectedLabels}
        onClose={() => setAddModalOpen(false)}
        onAdd={handleAddStrategies}
      />
    </div>
  );
}
