import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Toolbar } from "../../components/history/Toolbar";
import { RunTable } from "../../components/history/RunTable";
import { Pager } from "../../components/ui/Pager";
import { Button } from "../../components/ui/Button";

import {
  defaultHistoryFilter,
  fallbackRunsList,
  listRuns,
  toggleFavorite,
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
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  // Tracks which runs have been optimistically flipped relative to their server baseline
  const [flipped, setFlipped] = useState<Record<string, boolean>>({});
  const apiEnabled = import.meta.env.MODE !== "test";
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: qk.runs.list(filter),
    queryFn: () => listRuns(filter),
    enabled: apiEnabled,
  });

  const favoriteMutation = useMutation({
    mutationFn: (runId: string) => toggleFavorite(runId),
    onSuccess: (_data, runId) => {
      // Server now matches local — clear the flip flag and refetch
      setFlipped((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
      void queryClient.invalidateQueries({ queryKey: qk.runs.list(filter) });
      void queryClient.invalidateQueries({ queryKey: qk.runs.detail(runId) });
    },
    onError: (_err, runId) => {
      // Roll back the optimistic flip
      setFlipped((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
    },
  });

  const handleToggleFavorite = (runId: string) => {
    setFlipped((prev) => ({ ...prev, [runId]: !prev[runId] }));
    if (apiEnabled) favoriteMutation.mutate(runId);
  };

  const applyLocalFavorite = (row: RunRow): RunRow =>
    flipped[row.run_id]
      ? { ...row, favorited: !(row.favorited ?? false) }
      : row;

  // Server returns already-paginated items. Fallback is the full list — we
  // filter & paginate client-side so the demo works without an API.
  const now = useMemo(() => Date.now(), []);
  const serverData = query.data;
  const { rows, total } = useMemo(() => {
    if (apiEnabled && serverData) {
      return { rows: serverData.items.map(applyLocalFavorite), total: serverData.total };
    }
    const filtered = filterRows(fallbackRunsList, filter, now);
    const start = (filter.page - 1) * filter.pageSize;
    return {
      rows: filtered.slice(start, start + filter.pageSize).map(applyLocalFavorite),
      total: filtered.length,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiEnabled, serverData, filter, now, flipped]);

  const handleRerun = () => {
    if (selectedId) onNavigate("backtest", selectedId);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: 24 }}>
      <Toolbar filter={filter} onChange={setFilter} total={total} />

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, alignItems: "center" }}>
        {selectedId && (
          <span className="mono muted" style={{ fontSize: 11 }}>
            Selected · {selectedId}
          </span>
        )}
        <Button
          variant={selectedId ? "gold" : "outline-muted"}
          size="sm"
          disabled={!selectedId}
          onClick={handleRerun}
        >
          ▶ RE-RUN SELECTED
        </Button>
      </div>

      <RunTable
        rows={rows}
        selectedId={selectedId}
        onSelect={(id) => setSelectedId((prev) => (prev === id ? undefined : id))}
        onToggleFavorite={handleToggleFavorite}
      />

      <Pager
        total={total}
        page={filter.page}
        pageSize={filter.pageSize}
        onChange={(p) => setFilter({ ...filter, page: p })}
      />
    </div>
  );
}
