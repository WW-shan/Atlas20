// Paired with useRunBacktest — both manipulate the same queue cache.
import { useQuery } from "@tanstack/react-query";

import { listRunsQueue, type RunRowSummary } from "../../lib/api";
import { qk } from "../../lib/qk";

const ACTIVE_POLL_MS = 2000;

function hasActiveRuns(runs: RunRowSummary[] | undefined): boolean {
  return (runs ?? []).some((run) => run.status === "queued" || run.status === "running");
}

export function useRunQueue() {
  return useQuery({
    queryKey: qk.runs.queue(),
    queryFn: listRunsQueue,
    // Poll only while something is in flight. useRunBacktest writes each
    // submitted run into this cache, which re-evaluates the interval and
    // resumes polling; an idle queue no longer hits the API every 2s forever.
    refetchInterval: (query) => (hasActiveRuns(query.state.data) ? ACTIVE_POLL_MS : false),
    refetchIntervalInBackground: true,
  });
}
