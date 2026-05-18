// ============================================================
// TanStack Query Key Registry
// SPEC §9 — single source of truth for query keys
// ============================================================

import type { ChartRange, ReportSortKey } from "../components/ui/types";
import type { HistoryFilter } from "./api";

// Canonicalize history filter to ensure key stability
// (sorts chips alphabetically so semantically equal filters share cache)
function canonicalizeFilter(f: HistoryFilter): HistoryFilter {
  return { ...f, chips: [...f.chips].sort() };
}

export const qk = {
  overview: () => ["overview"] as const,
  options: () => ["options"] as const,

  runs: {
    queue:  () => ["runs", "queue"] as const,
    list:   (f: HistoryFilter) => ["runs", "list", canonicalizeFilter(f)] as const,
    detail: (id: string) => ["runs", "detail", id] as const,
  },

  compare: (ids: string[], range: ChartRange) =>
    ["compare", [...ids].sort(), range] as const,

  universe: {
    timeline: () => ["universe", "timeline"] as const,
    sources:  () => ["universe", "sources"] as const,
    alerts:   () => ["universe", "alerts"] as const,
  },

  reports: {
    featured: () => ["reports", "featured"] as const,
    archive:  (sort: ReportSortKey) => ["reports", "archive", sort] as const,
  },
};
