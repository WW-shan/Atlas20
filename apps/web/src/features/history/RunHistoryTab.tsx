import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Toolbar } from "../../components/history/Toolbar";
import { RunTable } from "../../components/history/RunTable";
import { Pager } from "../../components/ui/Pager";

import {
  defaultHistoryFilter,
  fallbackRunsList,
  listRuns,
} from "../../lib/api";
import type { HistoryFilter, RunRow } from "../../lib/api";
import type { ConsoleTab } from "../../components/navigation/TabSwitcher";
import { qk } from "../../lib/qk";

type Props = {
  onNavigate: (tab: ConsoleTab, prefillRunId?: string) => void;
};

const DAY_MS = 24 * 60 * 60 * 1000;

function withinDateRange(iso: string, range: HistoryFilter["dateRange"], now = Date.now()): boolean {
  if (range === "all") return true;
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return false;
  if (range === "ytd") {
    const start = new Date(new Date(now).getFullYear(), 0, 1).getTime();
    return ts >= start;
  }
  const days = range === "7d" ? 7 : range === "30d" ? 30 : 90;
  return ts >= now - days * DAY_MS;
}

function matchesChips(row: RunRow, chips: string[]): boolean {
  if (chips.length === 0) return true;
  return chips.every((chip) => {
    if (chip === "favorited") return Boolean(row.favorited);
    if (["queued", "running", "completed", "failed"].includes(chip)) return row.status === chip;
    return row.strategy_family === chip || row.strategy.includes(chip);
  });
}

function matchesQuery(row: RunRow, q: string): boolean {
  if (!q) return true;
  const needle = q.toLowerCase();
  return (
    row.run_id.toLowerCase().includes(needle) ||
    row.strategy.toLowerCase().includes(needle) ||
    row.universe.toLowerCase().includes(needle)
  );
}

function filterRows(rows: RunRow[], f: HistoryFilter, now: number): RunRow[] {
  return rows.filter((r) =>
    matchesQuery(r, f.q) &&
    matchesChips(r, f.chips) &&
    withinDateRange(r.created_at, f.dateRange, now),
  );
}

export function RunHistoryTab({ onNavigate }: Props) {
  const [filter, setFilter] = useState<HistoryFilter>(defaultHistoryFilter);
  const apiEnabled = import.meta.env.MODE !== "test";

  const query = useQuery({
    queryKey: qk.runs.list(filter),
    queryFn: () => listRuns(filter),
    enabled: apiEnabled,
  });

  // For fallback (and tests), filter client-side. Server-mode trusts the API.
  const now = useMemo(() => Date.now(), []);
  const serverData = query.data;
  const { items, total } = useMemo(() => {
    if (apiEnabled && serverData) {
      return { items: serverData.items, total: serverData.total };
    }
    const filtered = filterRows(fallbackRunsList, filter, now);
    return { items: filtered, total: filtered.length };
  }, [apiEnabled, serverData, filter, now]);

  const start = (filter.page - 1) * filter.pageSize;
  const pageRows = items.slice(start, start + filter.pageSize);

  const handleOpen = (runId: string) => {
    onNavigate("backtest", runId);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: 24 }}>
      <Toolbar filter={filter} onChange={setFilter} total={total} />
      <RunTable rows={pageRows} onOpen={handleOpen} />
      <Pager
        total={total}
        page={filter.page}
        pageSize={filter.pageSize}
        onChange={(p) => setFilter({ ...filter, page: p })}
      />
    </div>
  );
}
