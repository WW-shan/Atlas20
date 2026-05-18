import { useMutation } from "@tanstack/react-query";

import { runBacktest } from "../../lib/api";
import type { BacktestConfig } from "../../lib/api";
import type { DashboardFormState } from "./useChampionPreset";

// NOTE: This module is slated for deletion in Phase 6 (page2 implementation).
// The cast bridges the legacy DashboardFormState shape to the new BacktestConfig.
export function useRunBacktest() {
  return useMutation({
    mutationFn: (payload: DashboardFormState) =>
      runBacktest(payload as unknown as BacktestConfig),
  });
}
