import { useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

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

import { describeApiError, fallbackOptions, getCompare, getOptions } from "../../lib/api";
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
    // Keep the static fallback visible as placeholderData so the AddStrategy
    // modal's preset list is never empty while /api/options is loading.
    // Unlike initialData it is never written to the shared options cache and
    // it disappears on error, so the seeding effect below only ever consumes
    // a real backend response (never the hardcoded fallback labels).
    placeholderData: fallbackOptions,
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
    // Only a successful network response may seed; the placeholder fallback
    // stays visible for the AddStrategy modal during load but never seeds.
    if (!options.isSuccess || options.isPlaceholderData) return;
    const seeded = buildSelectionsFromPresets(options.data?.presets, 3);
    if (seeded.length === 0) return;
    seededRef.current = true;
    setSelections(seeded);
  }, [options.isSuccess, options.isPlaceholderData, options.data?.presets, initialSelections, selections.length]);

  const query = useQuery({
    queryKey: qk.compare(ids, range),
    queryFn: () => getCompare(ids, range),
    enabled: hasSelections,
    // While a new range/selection loads, keep the last real comparison on
    // screen (with the loading bar) instead of the static demo payload,
    // whose holdings overlap and strategies are not the user's selection.
    placeholderData: keepPreviousData,
  });

  const compareFailed = query.isError || query.isRefetchError;
  const compareLoading = hasSelections && query.isFetching;
  const data = query.data;
  const strategyOptions = useMemo(() => {
    const strategyLabels = (options.data?.strategies ?? []).map((s) => s.display_name);
    const presetLabels = (options.data?.presets ?? []).map((p) => p.display_name);
    return Array.from(new Set([...selections.map((s) => s.label), ...strategyLabels, ...presetLabels]));
  }, [options.data?.strategies, options.data?.presets, selections]);

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
    const strategyByLabel = new Map((options.data?.strategies ?? []).map((s) => [s.display_name, s.strategy]));
    setSelections((current) => {
      // Existing selections keep their id and line color: re-deriving the id
      // from the display label breaks when options changed since they were
      // added (the label then became the id sent to /api/compare).
      const resolved = labels.map((label) => {
        const existing = current.find((selection) => selection.label === label);
        return existing ?? { id: strategyByLabel.get(label) ?? presetByLabel.get(label) ?? label, label, tone: undefined };
      });
      const usedTones = new Set(resolved.flatMap((item) => (item.tone ? [item.tone] : [])));
      const freeTones = TONES.filter((tone) => !usedTones.has(tone));
      let nextFree = 0;
      return resolved.map((item, index) => ({
        ...item,
        tone: item.tone ?? freeTones[nextFree++] ?? TONES[index % TONES.length],
      }));
    });
    setAddModalOpen(false);
  };

  return (
    <div className="compare-tab">
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

      {options.isError && (
        <ErrorBanner
          message={describeApiError(options.error, "Unable to load strategy options")}
          onRetry={() => { void options.refetch(); }}
        />
      )}

      {!hasSelections ? (
        <EmptyState
          title="No strategies selected"
          action={{ label: "Add strategy", onClick: () => setAddModalOpen(true) }}
        />
      ) : (
        <>
          {compareFailed && (
            <ErrorBanner
              message={describeApiError(query.error, "Unable to load strategy comparison")}
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
      <div className={selections.length > 3 ? "compare-metrics-grid compare-metrics-grid--single" : "compare-metrics-grid"}>
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
