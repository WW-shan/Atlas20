import { useQuery } from "@tanstack/react-query";

import { listRunsQueue } from "../../lib/api";
import { qk } from "../../lib/qk";

export function useRunQueue() {
  return useQuery({
    queryKey: qk.runs.queue(),
    queryFn: listRunsQueue,
  });
}
