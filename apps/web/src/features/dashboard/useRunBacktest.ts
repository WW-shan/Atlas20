import { useMutation } from "@tanstack/react-query";

import { runBacktest } from "../../lib/api";
import type { DashboardFormState } from "./useChampionPreset";

export function useRunBacktest() {
  return useMutation({
    mutationFn: (payload: DashboardFormState) => runBacktest(payload),
  });
}
