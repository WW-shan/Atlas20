import { useEffect, useReducer, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

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
  describeApiError,
  generateReport,
  getOptions,
  getRunDetail,
  isBacktestRun,
  listRuns,
  RESEARCH_UNIVERSE_TOP_N,
  type BacktestConfig,
  type HistoryFilter,
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

// Server-side "completed" filter so failed/queued rows can't use up the page;
// 50 rows leaves room for daily universe_refresh jobs, which also complete.
const RECENT_COMPLETED_RUNS: HistoryFilter = { q: "", chips: ["completed"], dateRange: "all", page: 1, pageSize: 50 };

function hydrateFromDetail(detail: RunDetailPayload): BacktestConfig {
  // Re-runs always use the point-in-time Top 20 (AGENTS.md), even when the
  // source run predates that constraint (e.g. a legacy "Top-10" run).
  return {
    ...defaultBacktestConfig,
    preset: isBacktestRun(detail) ? detail.strategy : defaultBacktestConfig.preset,
    universe: { ...defaultBacktestConfig.universe, topN: RESEARCH_UNIVERSE_TOP_N },
    window: {
      ...defaultBacktestConfig.window,
      start: detail.window.start,
      end: detail.window.end,
    },
  };
}

export function BacktestStudioTab({ prefillRunId, onNavigate }: Props) {
  const [config, dispatch] = useReducer(reducer, defaultBacktestConfig);
  const [submittedRunId, setSubmittedRunId] = useState<string | undefined>(undefined);
  const [reportPending, setReportPending] = useState(false);
  const [reportToast, setReportToast] = useState<string | undefined>(undefined);
  const [reportError, setReportError] = useState<string | undefined>(undefined);
  const queryClient = useQueryClient();
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
  // though plenty of past runs exist. Ask the server for completed runs and
  // pick the first actual backtest — skipping `universe_refresh` and other
  // background jobs that don't have a return_pct to plot.
  const recentRunsQuery = useQuery({
    queryKey: qk.runs.list(RECENT_COMPLETED_RUNS),
    queryFn: () => listRuns(RECENT_COMPLETED_RUNS),
    staleTime: 60 * 1000,
  });

  // Default to the most recent run instead of a hardcoded synthetic id. An
  // id that doesn't exist would 404 here and the UI would show ghost KPIs
  // (we previously had a literal "btk_0142" fallback that surfaced fake
  // numbers for every fresh visit). Fallback chain:
  //   explicit prefillRunId  →  first run in queue (in-flight)
  //                          →  most recent COMPLETED backtest in history
  //                          →  undefined (honest empty state)
  // Filtering on status === "completed" (and return_pct present) prevents
  // failed runs from prefilling — their detail payload turns into all
  // zeros downstream, which would surface as ghost "CAGR 0%, Sharpe 0"
  // KPIs as if the strategy had a flat year.
  const latestQueueRunId = queue.data?.find(isBacktestRun)?.run_id;
  const latestHistoryRunId = recentRunsQuery.data?.items
    .find((row) => isBacktestRun(row) && row.status === "completed" && row.return_pct != null)?.run_id;
  const selectedRunId = prefillRunId ?? submittedRunId ?? latestQueueRunId ?? latestHistoryRunId;
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

  const previousQueueRunIds = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!queue.data) return;

    const currentQueueRunIds = new Set(queue.data.map((run) => run.run_id));
    if (
      submittedRunId &&
      previousQueueRunIds.current.has(submittedRunId) &&
      !currentQueueRunIds.has(submittedRunId)
    ) {
      void queryClient.invalidateQueries({ queryKey: qk.runs.listAll() });
      void queryClient.invalidateQueries({ queryKey: qk.runs.detail(submittedRunId) });
      void queryClient.invalidateQueries({ queryKey: ["reports", "archive"] });
      void queryClient.invalidateQueries({ queryKey: qk.reports.featured() });
      void recentRunsQuery.refetch();
      setReportToast(`Backtest completed: ${submittedRunId}`);
    }
    previousQueueRunIds.current = currentQueueRunIds;
  }, [queryClient, queue.data, recentRunsQuery, submittedRunId]);

  useEffect(() => {
    if (!reportToast) return;
    const timer = window.setTimeout(() => setReportToast(undefined), 4000);
    return () => window.clearTimeout(timer);
  }, [reportToast]);

  const handleRegenerateReport = () => {
    if (!detailData || reportPending) return;
    setReportPending(true);
    setReportError(undefined);
    void generateReport({
      type: "run",
      run_id: detailData.run_id,
      formats: ["markdown", "pdf", "png", "bundle"],
    })
      .then((response) => {
        setReportToast(response.warnings.length > 0 ? response.warnings.join("; ") : "Report regenerated");
      })
      .catch((error: unknown) => setReportError(describeApiError(error, "Unable to regenerate report")))
      .finally(() => setReportPending(false));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: 24, height: "calc(100vh - var(--topnav-h) - var(--space-6) - var(--pageheader-h))", overflow: "hidden" }}>
      {reportToast && <Toast>{reportToast}</Toast>}
      {reportError && <ErrorBanner message={reportError} />}

      {/* Mini page header with RUN ID pill + NEW RUN button */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, flexShrink: 0 }}>
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
        <Button
          variant="gold"
          onClick={() => {
            hydratedFor.current = undefined;
            setSubmittedRunId(undefined);
            runMutation.reset();
            setReportError(undefined);
            dispatch({ type: "reset" });
          }}
        >
          + NEW RUN
        </Button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr 320px", gap: 16, flex: 1, minHeight: 0, alignItems: "stretch" }}>
        <div style={{ overflowY: "auto", minHeight: 0, display: "flex", flexDirection: "column", gap: 12 }}>
          {runMutation.isError && (
            <ErrorBanner message={describeApiError(runMutation.error, "Unable to queue backtest")} />
          )}
          {isInitialDetailLoading ? (
            <DetailPrefillSkeleton />
          ) : (
            <ParameterSidebar
              value={config}
              onChange={(next) => dispatch({ type: "set", patch: next })}
              onRun={() => {
                runMutation.mutate(config, {
                  onSuccess: (run) => {
                    setSubmittedRunId(run.run_id);
                    setReportToast(`Backtest queued: ${run.run_id}`);
                  },
                });
              }}
              isRunning={runMutation.isPending}
              refreshing={isDetailRefreshing}
              presets={optionsQuery.data?.presets}
            />
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
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
