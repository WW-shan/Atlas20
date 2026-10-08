import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runBacktest, type BacktestConfig, type RunRowSummary } from "../../lib/api";
import { qk } from "../../lib/qk";

export function useRunBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: BacktestConfig) => runBacktest(payload),
    onSuccess: async (result: RunRowSummary) => {
      // A queue poll that started before this run was committed would land
      // after the write below and drop the run (faking a "completed"
      // transition and stopping the idle-aware polling). Cancel it first.
      await queryClient.cancelQueries({ queryKey: qk.runs.queue() });
      queryClient.setQueryData<RunRowSummary[]>(qk.runs.queue(), (prev = []) => [
        result,
        ...prev.filter((run) => run.run_id !== result.run_id),
      ]);
      void queryClient.invalidateQueries({ queryKey: qk.runs.listAll() });
    },
  });
}
