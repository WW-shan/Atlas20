import { useQuery } from "@tanstack/react-query";

import { listRunsQueue, fallbackRunsQueue } from "../../lib/api";
import { qk } from "../../lib/qk";

export function useRunQueue() {
  return useQuery({
    queryKey: qk.runs.queue(),
    queryFn: listRunsQueue,
    initialData: fallbackRunsQueue,
    placeholderData: fallbackRunsQueue,
    enabled: import.meta.env.MODE !== "test",
  });
}
