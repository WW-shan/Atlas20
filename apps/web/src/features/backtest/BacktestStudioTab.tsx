import { useEffect, useReducer, useRef } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ConsoleTab } from "../../components/navigation/TabSwitcher";
import { Pill } from "../../components/ui/Pill";
import { Button } from "../../components/ui/Button";
import { ParameterSidebar } from "../../components/backtest/ParameterSidebar";
import { EquityWorkspace } from "../../components/backtest/EquityWorkspace";
import { RunQueue } from "../../components/backtest/RunQueue";
import {
  defaultBacktestConfig,
  fallbackRunDetail,
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
  const isCanonical = selectedRunId === fallbackRunDetail.run_id;
  const detailQuery = useQuery({
    queryKey: qk.runs.detail(selectedRunId),
    queryFn: () => getRunDetail(selectedRunId),
    initialData: isCanonical ? fallbackRunDetail : undefined,
    placeholderData: isCanonical ? fallbackRunDetail : undefined,
    enabled: import.meta.env.MODE !== "test",
  });
  const detail: RunDetailPayload = detailQuery.data ?? fallbackRunDetail;

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
          RUN ID: <span className="mono" style={{ marginLeft: 4 }}>{detail.run_id}</span>
        </Pill>
        <Button variant="gold" onClick={() => { hydratedFor.current = undefined; dispatch({ type: "reset" }); }}>+ NEW RUN</Button>
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <ParameterSidebar
          value={config}
          onChange={(next) => dispatch({ type: "set", patch: next })}
          onRun={() => runMutation.mutate(config)}
          isRunning={runMutation.isPending}
        />

        <EquityWorkspace detail={detail} />

        <RunQueue runs={queue.data ?? []} onViewAll={() => onNavigate("history")} />
      </div>
    </div>
  );
}
