import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import type { ConsoleTab } from "../../components/navigation/TabSwitcher";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { Pill } from "../../components/ui/Pill";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { Skeleton } from "../../components/ui/Skeleton";
import type { RunStatusEnum } from "../../components/ui/types";
import {
  defaultBacktestConfig,
  fallbackOptions,
  getOptions,
  getStrategyLabBatch,
  submitStrategyLabBatch,
} from "../../lib/api";
import type { BacktestConfig, StrategyLabBatchPayload } from "../../lib/api";
import { qk } from "../../lib/qk";
import { StrategyLabControls } from "./StrategyLabControls";
import { StrategyLabResultsTable, type StrategyLabSortMetric } from "./StrategyLabResultsTable";

type Props = {
  onNavigate: (tab: ConsoleTab, prefillRunId?: string) => void;
};

const terminalStatuses: RunStatusEnum[] = ["completed", "failed", "cancelled"];

export function StrategyLabTab({ onNavigate }: Props) {
  const options = useQuery({
    queryKey: qk.options(),
    queryFn: getOptions,
    initialData: fallbackOptions,
    staleTime: 5 * 60 * 1000,
  });
  const optionData = options.data ?? fallbackOptions;
  const [selectedPresets, setSelectedPresets] = useState<string[]>([fallbackOptions.presets[0]?.slug ?? "base"]);
  const [selectedTopNs, setSelectedTopNs] = useState<number[]>([10, 20]);
  const [selectedRebalances, setSelectedRebalances] = useState<BacktestConfig["window"]["rebalance"][]>(["Monthly"]);
  const [batchId, setBatchId] = useState<string | undefined>();
  const [queuedMessage, setQueuedMessage] = useState<string | undefined>();
  const [sortMetric, setSortMetric] = useState<StrategyLabSortMetric>("sharpe");

  const runCount = selectedPresets.length * selectedTopNs.length * selectedRebalances.length;
  const submitDisabled = runCount === 0 || runCount > 24;
  const batch = useQuery({
    queryKey: qk.strategyLab.batch(batchId ?? "__none__"),
    queryFn: () => getStrategyLabBatch(batchId as string),
    enabled: !!batchId,
    refetchInterval: (query) => {
      const data = query.state.data as StrategyLabBatchPayload | undefined;
      return hasActiveRuns(data) ? 5000 : false;
    },
  });
  const submitMutation = useMutation({
    mutationFn: submitStrategyLabBatch,
    onSuccess: (response) => {
      setBatchId(response.batch_id);
      setQueuedMessage(`${response.total} runs queued`);
    },
  });

  const batchData = batch.data;
  const statusCounts = batchData?.status_counts;
  const completedCount = statusCounts?.completed ?? 0;
  const terminalCount = terminalStatuses.reduce((total, status) => total + (statusCounts?.[status] ?? 0), 0);
  const totalRuns = batchData?.runs.length ?? 0;
  const completionLabel = totalRuns > 0 ? `${terminalCount}/${totalRuns} terminal` : "No batch selected";

  const togglePreset = (slug: string) => setSelectedPresets((current) => toggleValue(current, slug));
  const toggleTopN = (topN: number) => setSelectedTopNs((current) => toggleValue(current, topN));
  const toggleRebalance = (rebalance: BacktestConfig["window"]["rebalance"]) => {
    setSelectedRebalances((current) => toggleValue(current, rebalance));
  };

  const request = useMemo(() => ({
    presets: selectedPresets,
    topNs: selectedTopNs,
    rebalances: selectedRebalances,
    baseConfig: defaultBacktestConfig,
  }), [selectedPresets, selectedTopNs, selectedRebalances]);

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      <StrategyLabControls
        options={optionData}
        selectedPresets={selectedPresets}
        selectedTopNs={selectedTopNs}
        selectedRebalances={selectedRebalances}
        runCount={runCount}
        pending={submitMutation.isPending}
        disabled={submitDisabled}
        onTogglePreset={togglePreset}
        onToggleTopN={toggleTopN}
        onToggleRebalance={toggleRebalance}
        onSubmit={() => submitMutation.mutate(request)}
      />

      {runCount > 24 && (
        <ErrorBanner message="Strategy Lab can queue at most 24 runs per batch." />
      )}
      {submitMutation.isError && (
        <ErrorBanner
          message="Unable to queue Strategy Lab experiment."
          onRetry={() => submitMutation.mutate(request)}
        />
      )}

      <Card ariaLabel="Strategy Lab batch status">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <SectionHeader>Batch status</SectionHeader>
          <span className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>
            {batchId ?? "—"}
          </span>
        </div>
        {queuedMessage && <p style={{ margin: "8px 0 0", color: "var(--text)" }}>{queuedMessage}</p>}
        {batch.isLoading && <Skeleton variant="card" height="52px" />}
        {batch.isError && (
          <ErrorBanner
            message="Unable to load Strategy Lab batch."
            onRetry={() => { void batch.refetch(); }}
          />
        )}
        {batchData ? (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 12 }}>
            <Pill tone="muted" size="xs">queued {statusCounts?.queued ?? 0}</Pill>
            <Pill tone="cyan" size="xs" pulse={(statusCounts?.running ?? 0) > 0}>running {statusCounts?.running ?? 0}</Pill>
            <Pill tone="emerald" size="xs">completed {completedCount}</Pill>
            <Pill tone="rose" size="xs">failed {statusCounts?.failed ?? 0}</Pill>
            <Pill tone="muted" size="xs">cancelled {statusCounts?.cancelled ?? 0}</Pill>
            <span className="muted" style={{ marginLeft: "auto", fontSize: 12 }}>{completionLabel}</span>
          </div>
        ) : (
          !batch.isLoading && <EmptyState title="No experiment batch queued yet" />
        )}
      </Card>

      <StrategyLabResultsTable
        results={batchData?.results ?? []}
        sortMetric={sortMetric}
        onSortMetricChange={setSortMetric}
        onOpenRun={(runId) => onNavigate("backtest", runId)}
      />
    </div>
  );
}

function toggleValue<T>(values: T[], value: T): T[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function hasActiveRuns(data: StrategyLabBatchPayload | undefined): boolean {
  if (!data) return false;
  return (data.status_counts.queued ?? 0) > 0 || (data.status_counts.running ?? 0) > 0;
}
