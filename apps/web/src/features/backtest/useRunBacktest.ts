import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runBacktest, type BacktestConfig, type RunRowSummary } from "../../lib/api";
import { qk } from "../../lib/qk";

export function useRunBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: BacktestConfig) => runBacktest(payload),
    onSuccess: (result: RunRowSummary) => {
      const prev = queryClient.getQueryData<RunRowSummary[]>(qk.runs.queue()) ?? [];
      queryClient.setQueryData<RunRowSummary[]>(qk.runs.queue(), [result, ...prev]);
      void queryClient.invalidateQueries({ queryKey: qk.runs.listAll() });
    },
  });
}
