import { useEffect, useReducer, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ConsoleTab } from "../../components/navigation/TabSwitcher";
import { Pill } from "../../components/ui/Pill";
import { Button } from "../../components/ui/Button";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { Skeleton } from "../../components/ui/Skeleton";
import { Toast } from "../../components/ui/Toast";
import { ParameterSidebar } from "../../components/backtest/ParameterSidebar";
import { EquityWorkspace } from "../../components/backtest/EquityWorkspace";
import { RunQueue } from "../../components/backtest/RunQueue";
import {
  defaultBacktestConfig,
  generateReport,
  getOptions,
  getRunDetail,
  listRuns,
  type BacktestConfig,
  type RunDetailPayload,
} from "../../lib/api";
import { qk } from "../../lib/qk";
import { useRunBacktest } from "./useRunBacktest";
import { useRunQueue } from "./useRunQueue";

type Props = {
  prefillRunId?: string;
  onNavigate: (tab: ConsoleTab, prefillRunId?: string) => void;
};

type Action =
  | { type: "set"; patch: Partial<BacktestConfig> }
  | { type: "reset" }
  | { type: "hydrate"; config: BacktestConfig };

function reducer(state: BacktestConfig, action: Action): BacktestConfig {
  if (action.type === "reset") return defaultBacktestConfig;
  if (action.type === "hydrate") return action.config;
  return { ...state, ...action.patch };
}

function hydrateFromDetail(detail: RunDetailPayload): BacktestConfig {
  const topNMatch = detail.universe.match(/(\d+)/);
  const topN = topNMatch ? Math.min(50, Math.max(1, Number(topNMatch[1]))) : defaultBacktestConfig.universe.topN;
  return {
    ...defaultBacktestConfig,
    preset: detail.strategy,
    universe: { ...defaultBacktestConfig.universe, topN },
    window: {
      ...defaultBacktestConfig.window,
      start: detail.window.start,
      end: detail.window.end,
    },
  };
}

export function BacktestStudioTab({ prefillRunId, onNavigate }: Props) {
  const [config, dispatch] = useReducer(reducer, defaultBacktestConfig);
  const [reportPending, setReportPending] = useState(false);
  const [reportToast, setReportToast] = useState<string | undefined>(undefined);
  const runMutation = useRunBacktest();
  const queue = useRunQueue();
  const optionsQuery = useQuery({
    queryKey: qk.options(),
    queryFn: getOptions,
    staleTime: 5 * 60 * 1000,
  });
  // Latest backtest run from history, used as a graceful prefill fallback
  // when no run is currently in flight (queue is empty). Without this, a
  // fresh visit to Backtest would show "—" and an empty workspace even
  // though plenty of past runs exist. Pull a small page and pick the first
  // entry that's an actual backtest — skipping `universe_refresh` and other
  // background jobs that don't have a return_pct to plot.
  const recentRunsQuery = useQuery({
    queryKey: qk.runs.list({ q: "", chips: [], dateRange: "30d", page: 1, pageSize: 10 }),
    queryFn: () => listRuns({ q: "", chips: [], dateRange: "30d", page: 1, pageSize: 10 }),
    staleTime: 60 * 1000,
  });

  // Default to the most recent run instead of a hardcoded synthetic id. An
  // id that doesn't exist would 404 here and the UI would show ghost KPIs
  // (we previously had a literal "btk_0142" fallback that surfaced fake
  // numbers for every fresh visit). Fallback chain:
  //   explicit prefillRunId  →  first run in queue (in-flight)
  //                          →  most recent backtest in history
  //                          →  undefined (honest empty state)
  const latestQueueRunId = queue.data?.[0]?.run_id;
  const latestHistoryRunId = recentRunsQuery.data?.items
    .find((row) => row.strategy !== "universe_refresh")?.run_id;
  const selectedRunId = prefillRunId ?? latestQueueRunId ?? latestHistoryRunId;
  const detailQuery = useQuery({
    queryKey: qk.runs.detail(selectedRunId ?? "__none__"),
    queryFn: () => getRunDetail(selectedRunId as string),
    enabled: !!selectedRunId,
  });
  const detailData = detailQuery.data;
  const isInitialDetailLoading = !!selectedRunId && detailQuery.isLoading && detailData === undefined;
  const isDetailRefreshing = detailQuery.isFetching && detailData !== undefined;

  // When user clicks RE-RUN from history, hydrate the sidebar from that run's detail.
  const hydratedFor = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!prefillRunId || hydratedFor.current === prefillRunId) return;
    if (detailQuery.data && detailQuery.data.run_id === prefillRunId) {
      dispatch({ type: "hydrate", config: hydrateFromDetail(detailQuery.data) });
      hydratedFor.current = prefillRunId;
    }
  }, [prefillRunId, detailQuery.data]);

  useEffect(() => {
    if (!reportToast) return;
    const timer = window.setTimeout(() => setReportToast(undefined), 4000);
    return () => window.clearTimeout(timer);
  }, [reportToast]);

  const handleRegenerateReport = () => {
    if (!detailData || reportPending) return;
    setReportPending(true);
    void generateReport({
      type: "run",
      run_id: detailData.run_id,
      formats: ["markdown", "pdf", "png", "bundle"],
    })
      .then((response) => {
        setReportToast(response.warnings.length > 0 ? response.warnings.join("; ") : "Report regenerated");
      })
      .catch(() => setReportToast("Report regeneration failed"))
      .finally(() => setReportPending(false));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: 24 }}>
      {reportToast && <Toast>{reportToast}</Toast>}

      {/* Mini page header with RUN ID pill + NEW RUN button */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12 }}>
        <Pill tone="cyan-outline" size="sm">
          RUN ID: <span className="mono" style={{ marginLeft: 4 }}>{selectedRunId ?? "—"}</span>
        </Pill>
        <Button
          variant="outline-violet"
          loading={reportPending}
          disabled={!detailData}
          onClick={handleRegenerateReport}
        >
          Regenerate this run&apos;s report
        </Button>
        <Button variant="gold" onClick={() => { hydratedFor.current = undefined; dispatch({ type: "reset" }); }}>+ NEW RUN</Button>
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <div style={{ width: 340, flex: "0 0 340px", display: "flex", flexDirection: "column", gap: 12 }}>
          {isInitialDetailLoading ? (
            <DetailPrefillSkeleton />
          ) : (
            <ParameterSidebar
              value={config}
              onChange={(next) => dispatch({ type: "set", patch: next })}
              onRun={() => runMutation.mutate(config)}
              isRunning={runMutation.isPending}
              refreshing={isDetailRefreshing}
              presets={optionsQuery.data?.presets}
            />
          )}
        </div>

        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 16 }}>
          {isInitialDetailLoading && <WorkspaceSkeleton />}
          {detailQuery.isError && (
            <ErrorBanner
              message="Unable to load run detail."
              onRetry={() => { void detailQuery.refetch(); }}
            />
          )}
          {detailData && (
            <EquityWorkspace detail={detailData} />
          )}
        </div>

        {queue.isLoading && <RunQueueSkeleton />}
        {queue.isError && <RunQueueError onRetry={() => { void queue.refetch(); }} />}
        {queue.data && <RunQueue runs={queue.data} onViewAll={() => onNavigate("history")} />}
      </div>
    </div>
  );
}

function DetailPrefillSkeleton() {
  return (
    <div
      data-testid="backtest-detail-skeleton"
      style={{
        padding: 12,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
      aria-label="Backtest prefill loading"
    >
      <Skeleton variant="card" height="72px" />
    </div>
  );
}

function WorkspaceSkeleton() {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
      <Skeleton variant="card" height="360px" />
      <Skeleton variant="card" height="72px" />
    </div>
  );
}

function RunQueueSkeleton() {
  return (
    <aside
      data-testid="run-queue-skeleton"
      style={{
        width: 320,
        flex: "0 0 320px",
        padding: 20,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
      aria-label="Run queue loading"
    >
      <Skeleton variant="text" width="55%" />
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} variant="card" height="76px" />
      ))}
    </aside>
  );
}

function RunQueueError({ onRetry }: { onRetry: () => void }) {
  return (
    <aside
      style={{
        width: 320,
        flex: "0 0 320px",
        padding: 20,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
      }}
      aria-label="Run queue error"
    >
      <ErrorBanner message="Unable to load run queue." onRetry={onRetry} />
    </aside>
  );
}
