import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runBacktest, type BacktestConfig, type RunRowSummary } from "../../lib/api";
import { qk } from "../../lib/qk";

export function useRunBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: BacktestConfig) => runBacktest(payload),
    onSuccess: (result: RunRowSummary) => {
      // Optimistically push to queue
      const prev = queryClient.getQueryData<RunRowSummary[]>(qk.runs.queue()) ?? [];
      queryClient.setQueryData<RunRowSummary[]>(qk.runs.queue(), [result, ...prev]);
    },
  });
}
