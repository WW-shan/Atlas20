import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card } from "../../components/ui/Card";
import { DemoDataBanner } from "../../components/ui/DemoDataBanner";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { Skeleton } from "../../components/ui/Skeleton";
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

const RANGES: ChartRange[] = ["1M", "3M", "YTD", "1Y", "ALL"];
const TONES: CompareSelectionItem["tone"][] = ["gold", "violet", "cyan", "emerald"];

type Props = {
  initialSelections?: CompareSelectionItem[];
};

const lineToneFor = (tone: CompareSelectionItem["tone"]) => tone;

function buildSelectionsFromPresets(presets: { slug: string; display_name: string }[] | undefined, count: number): CompareSelectionItem[] {
  if (!presets || presets.length === 0) return [];
  return presets.slice(0, count).map((preset, index) => ({
    id: preset.slug,
    label: preset.display_name,
    tone: TONES[index % TONES.length],
  }));
}

export function StrategyCompareTab({ initialSelections }: Props = {}) {
  const [selections, setSelections] = useState<CompareSelectionItem[]>(initialSelections ?? []);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [range, setRange] = useState<ChartRange>("YTD");
  const ids = useMemo(() => selections.map((s) => s.id), [selections]);
  const hasSelections = selections.length > 0;
  const selectedLabels = useMemo(() => selections.map((selection) => selection.label), [selections]);

  const options = useQuery({
    queryKey: qk.options(),
    queryFn: getOptions,
    // Keep the static fallback visible as initialData so the AddStrategy
    // modal's preset list is never empty while /api/options is loading. The
    // seeding effect below explicitly waits for `isFetched && !isPending`
    // before consuming the data so it can distinguish "fallback placeholder"
    // from "real backend response" — without that gate, the seeding would
    // immediately fire with the hardcoded fallback labels.
    initialData: fallbackOptions,
  });

  // First-load: when no explicit initial selections were passed in props, seed
  // from the real /api/options presets list as soon as it resolves. Previously
  // this fell back to DEFAULT_SELECTIONS = ["ATLAS Adaptive v3", ...] which are
  // not actual strategy names; the backend's alias map silently resolved them
  // to real strategies but the UI labels lied.
  const seededRef = useRef(false);
  useEffect(() => {
    if (seededRef.current || initialSelections) return;
    if (selections.length > 0) {
      seededRef.current = true;
      return;
    }
    // `isFetched && !isPending` is true only once the network call returns,
    // which lets us reject the initialData fallback while still keeping it
    // visible for the AddStrategy modal during load.
    if (!options.isFetched || options.isPending) return;
    const seeded = buildSelectionsFromPresets(options.data?.presets, 3);
    if (seeded.length === 0) return;
    seededRef.current = true;
    setSelections(seeded);
  }, [options.isFetched, options.isPending, options.data?.presets, initialSelections, selections.length]);

  const query = useQuery({
    queryKey: qk.compare(ids, range),
    queryFn: () => getCompare(ids, range),
    enabled: hasSelections,
  });

  const compareFailed = query.isError || query.isRefetchError;
  const compareLoading = hasSelections && query.isFetching;
  const data = query.data ?? (compareFailed ? undefined : fallbackCompare);
  const strategyOptions = useMemo(() => {
    const presetLabels = (options.data?.presets ?? []).map((p) => p.display_name);
    return Array.from(new Set([...selections.map((s) => s.label), ...presetLabels]));
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
    const presetByLabel = new Map((options.data?.presets ?? []).map((p) => [p.display_name, p.slug]));
    setSelections((current) => labels.map((label, index) => {
      const id = presetByLabel.get(label) ?? label;
      const existing = current.find((selection) => selection.id === id);
      if (existing) return { ...existing, label };
      return { id, label, tone: TONES[index % TONES.length] };
    }));
    setAddModalOpen(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, padding: 24 }}>
      <DemoDataBanner visible={data?.data_source === "fallback"} />
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

      {!hasSelections ? (
        <EmptyState
          title="No strategies selected"
          action={{ label: "Add strategy", onClick: () => setAddModalOpen(true) }}
        />
      ) : (
        <>
          {compareFailed && (
            <ErrorBanner
              message="Unable to load strategy comparison."
              onRetry={() => { void query.refetch(); }}
            />
          )}
          {!data ? (
            compareLoading ? <Skeleton variant="card" height="320px" /> : null
          ) : (
            <>
              {compareLoading && <Skeleton variant="card" height="48px" />}

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

      {/* ===== Metrics + Overlap ===== */}
      <div style={{ display: "grid", gridTemplateColumns: selections.length > 3 ? "1fr" : "3fr 2fr", gap: 24 }}>
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

        {selections.length <= 3 && (
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
        )}
      </div>
      {selections.length > 3 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
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
      )}
            </>
          )}
        </>
      )}

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
