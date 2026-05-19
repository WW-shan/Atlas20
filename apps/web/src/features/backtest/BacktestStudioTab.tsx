import { useEffect, useReducer, useRef } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ConsoleTab } from "../../components/navigation/TabSwitcher";
import { Pill } from "../../components/ui/Pill";
import { Button } from "../../components/ui/Button";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { Skeleton } from "../../components/ui/Skeleton";
import { ParameterSidebar } from "../../components/backtest/ParameterSidebar";
import { EquityWorkspace } from "../../components/backtest/EquityWorkspace";
import { RunQueue } from "../../components/backtest/RunQueue";
import {
  defaultBacktestConfig,
  getRunDetail,
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
  const runMutation = useRunBacktest();
  const queue = useRunQueue();

  const selectedRunId = prefillRunId ?? "btk_0142";
  const detailQuery = useQuery({
    queryKey: qk.runs.detail(selectedRunId),
    queryFn: () => getRunDetail(selectedRunId),
  });

  // When user clicks RE-RUN from history, hydrate the sidebar from that run's detail.
  const hydratedFor = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!prefillRunId || hydratedFor.current === prefillRunId) return;
    if (detailQuery.data && detailQuery.data.run_id === prefillRunId) {
      dispatch({ type: "hydrate", config: hydrateFromDetail(detailQuery.data) });
      hydratedFor.current = prefillRunId;
    }
  }, [prefillRunId, detailQuery.data]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: 24 }}>

      {/* Mini page header with RUN ID pill + NEW RUN button */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12 }}>
        <Pill tone="cyan-outline" size="sm">
          RUN ID: <span className="mono" style={{ marginLeft: 4 }}>{selectedRunId}</span>
        </Pill>
        <Button variant="gold" onClick={() => { hydratedFor.current = undefined; dispatch({ type: "reset" }); }}>+ NEW RUN</Button>
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <div style={{ width: 340, flex: "0 0 340px", display: "flex", flexDirection: "column", gap: 12 }}>
          {detailQuery.isLoading && <DetailPrefillSkeleton />}
          <ParameterSidebar
            value={config}
            onChange={(next) => dispatch({ type: "set", patch: next })}
            onRun={() => runMutation.mutate(config)}
            isRunning={runMutation.isPending}
          />
        </div>

        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 16 }}>
          {detailQuery.isLoading && <WorkspaceSkeleton />}
          {detailQuery.isError && (
            <ErrorBanner
              message="Unable to load run detail."
              onRetry={() => { void detailQuery.refetch(); }}
            />
          )}
          {detailQuery.data && (
            <EquityWorkspace detail={detailQuery.data} />
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
