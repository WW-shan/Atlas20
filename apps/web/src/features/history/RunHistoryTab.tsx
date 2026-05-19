import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Toolbar } from "../../components/history/Toolbar";
import { RunTable } from "../../components/history/RunTable";
import { Pager } from "../../components/ui/Pager";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { Skeleton } from "../../components/ui/Skeleton";

import {
  defaultHistoryFilter,
  listRuns,
  toggleFavorite,
} from "../../lib/api";
import type { HistoryFilter, RunRow } from "../../lib/api";
import type { ConsoleTab } from "../../components/navigation/TabSwitcher";
import { qk } from "../../lib/qk";

type Props = {
  onNavigate: (tab: ConsoleTab, prefillRunId?: string) => void;
};

export function RunHistoryTab({ onNavigate }: Props) {
  const [filter, setFilter] = useState<HistoryFilter>(defaultHistoryFilter);
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  // Tracks which runs have been optimistically flipped relative to their server baseline
  const [flipped, setFlipped] = useState<Record<string, boolean>>({});
  const [favoriteRefetchId, setFavoriteRefetchId] = useState<string | undefined>(undefined);
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: qk.runs.list(filter),
    queryFn: () => listRuns(filter),
  });

  const favoriteMutation = useMutation({
    mutationFn: (runId: string) => toggleFavorite(runId),
    onSuccess: (data, runId) => {
      queryClient.setQueriesData<{ items: RunRow[]; total: number; page: number; pageSize: number }>(
        { queryKey: ["runs", "list"] },
        (old) => old
          ? {
              ...old,
              items: old.items.map((row) =>
                row.run_id === data.run_id ? { ...row, favorited: data.favorited } : row,
              ),
            }
          : old,
      );
      // Server now matches local — clear the flip flag and refetch
      setFlipped((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
      setFavoriteRefetchId(runId);
      void queryClient.invalidateQueries({ queryKey: ["runs", "list"] })
        .finally(() => setFavoriteRefetchId(undefined));
      void queryClient.invalidateQueries({ queryKey: qk.runs.detail(runId) });
    },
    onError: (_err, runId) => {
      // Roll back the optimistic flip
      setFlipped((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
      setFavoriteRefetchId(undefined);
    },
  });

  const handleToggleFavorite = (runId: string) => {
    if (favoriteMutation.isPending || favoriteRefetchId || query.isFetching) return;
    setFlipped((prev) => ({ ...prev, [runId]: !prev[runId] }));
    favoriteMutation.mutate(runId);
  };

  const applyLocalFavorite = (row: RunRow): RunRow =>
    flipped[row.run_id]
      ? { ...row, favorited: !(row.favorited ?? false) }
      : row;

  const serverData = query.data;
  const { rows, total } = useMemo(() => {
    return {
      rows: (serverData?.items ?? []).map(applyLocalFavorite),
      total: serverData?.total ?? 0,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverData, flipped]);
  const hasActiveFilter =
    filter.q.trim().length > 0 ||
    filter.chips.length > 0 ||
    filter.dateRange !== defaultHistoryFilter.dateRange;
  const favoriteBusyId =
    favoriteMutation.isPending && favoriteMutation.variables
      ? favoriteMutation.variables
      : favoriteRefetchId;
  const favoritesDisabled = Boolean(favoriteMutation.isPending || favoriteRefetchId || query.isFetching);

  const handleRerun = () => {
    if (selectedId) onNavigate("backtest", selectedId);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: 24 }}>
      <Toolbar filter={filter} onChange={setFilter} total={total} chipsDisabled={query.isLoading} />

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

      {query.isError && (
        <ErrorBanner
          message="Unable to load run history."
          onRetry={() => { void query.refetch(); }}
        />
      )}

      {query.isLoading && <RunHistorySkeleton />}

      {!query.isLoading && !query.isError && rows.length === 0 && (
        <EmptyState
          title={hasActiveFilter ? "No runs match these filters" : "No backtests yet"}
          action={hasActiveFilter ? { label: "Clear filters", onClick: () => setFilter(defaultHistoryFilter) } : undefined}
        />
      )}

      {!query.isLoading && rows.length > 0 && (
        <RunTable
          rows={rows}
          selectedId={selectedId}
          onSelect={(id) => setSelectedId((prev) => (prev === id ? undefined : id))}
          onToggleFavorite={handleToggleFavorite}
          favoriteBusyId={favoriteBusyId}
          favoritesDisabled={favoritesDisabled}
        />
      )}

      <Pager
        total={total}
        page={filter.page}
        pageSize={filter.pageSize}
        disabled={query.isLoading || query.isFetching}
        onChange={(p) => setFilter({ ...filter, page: p })}
      />
    </div>
  );
}

function RunHistorySkeleton() {
  return (
    <div
      role="region"
      aria-label="Run history table loading"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        overflowX: "auto",
      }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }} aria-label="Runs list loading">
        <tbody>
          {Array.from({ length: 5 }).map((_, i) => (
            <tr key={i} data-testid="run-history-skeleton-row">
              <td style={{ padding: "12px" }}>
                <Skeleton variant="text" height="18px" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
