import { useMemo, useState } from "react";

import { ChartWorkspace } from "../../components/dashboard/ChartWorkspace";
import { ParameterSidebar } from "../../components/dashboard/ParameterSidebar";
import { RunStatusRail } from "../../components/dashboard/RunStatusRail";
import type { OverviewPayload, RunStatus } from "../../lib/api";
import { championToFormState, type DashboardFormState } from "./useChampionPreset";
import { useRunBacktest } from "./useRunBacktest";

export function DashboardTab(props: { overview: OverviewPayload }) {
  const championPreset = useMemo(() => championToFormState(props.overview.champion), [props.overview.champion]);
  const [formState, setFormState] = useState<DashboardFormState>(championPreset);
  const [run, setRun] = useState<RunStatus | undefined>();
  const mutation = useRunBacktest();

  const handleRun = () => {
    mutation.mutate(formState, {
      onSuccess: (result) => setRun(result),
    });
  };

  return (
    <div className="dashboard-grid">
      <ParameterSidebar
        value={formState}
        onChange={setFormState}
        onResetChampion={() => setFormState(championPreset)}
        onRun={handleRun}
        isRunning={mutation.isPending}
      />
      <ChartWorkspace overview={props.overview} />
      <RunStatusRail champion={props.overview.champion} run={run} isRunning={mutation.isPending} />
    </div>
  );
}
