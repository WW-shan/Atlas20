import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Toolbar } from "../../components/history/Toolbar";
import type { HistoryViewMode } from "../../components/history/Toolbar";
import { RunTable } from "../../components/history/RunTable";
import { Pager } from "../../components/ui/Pager";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { Pill } from "../../components/ui/Pill";
import { Skeleton } from "../../components/ui/Skeleton";
import { SparklineChart } from "../../components/charts/SparklineChart";

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
  const [viewMode, setViewMode] = useState<HistoryViewMode>("list");
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
        { queryKey: qk.runs.listAll() },
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
      void queryClient.invalidateQueries({ queryKey: qk.runs.listAll() })
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
      <Toolbar
        filter={filter}
        onChange={setFilter}
        total={total}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        chipsDisabled={query.isLoading}
      />

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

      {!query.isLoading && rows.length > 0 && viewMode === "list" && (
        <RunTable
          rows={rows}
          selectedId={selectedId}
          onSelect={(id) => setSelectedId((prev) => (prev === id ? undefined : id))}
          onToggleFavorite={handleToggleFavorite}
          favoriteBusyId={favoriteBusyId}
          favoritesDisabled={favoritesDisabled}
        />
      )}

      {!query.isLoading && rows.length > 0 && viewMode === "grid" && (
        <RunGrid
          rows={rows}
          selectedId={selectedId}
          onSelect={(id) => setSelectedId((prev) => (prev === id ? undefined : id))}
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

function gridStatusTone(status: RunRow["status"]): { tone: "muted" | "cyan" | "emerald" | "rose"; pulse: boolean; label: string } {
  switch (status) {
    case "queued":    return { tone: "muted",   pulse: false, label: "queued" };
    case "running":   return { tone: "cyan",    pulse: true,  label: "running" };
    case "completed": return { tone: "emerald", pulse: false, label: "completed" };
    case "failed":    return { tone: "rose",    pulse: false, label: "failed" };
    case "cancelled": return { tone: "rose",    pulse: false, label: "CANCELLED" };
  }
}

function RunGrid({ rows, selectedId, onSelect }: { rows: RunRow[]; selectedId?: string; onSelect: (runId: string) => void }) {
  return (
    <div
      data-testid="run-history-grid"
      role="list"
      aria-label="Runs grid"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
        gap: 12,
      }}
    >
      {rows.map((row) => {
        const status = gridStatusTone(row.status);
        const isSelected = row.run_id === selectedId;
        const strategyLabel = row.selected_strategy ?? row.strategy;
        return (
          <div key={row.run_id} role="listitem">
            <Card
              ariaLabel={`Run ${row.run_id}`}
              style={{
                padding: 0,
                borderColor: isSelected ? "var(--violet)" : "var(--border)",
              }}
            >
              <button
                type="button"
                data-run-id={row.run_id}
                data-selected={isSelected ? "true" : undefined}
                aria-pressed={isSelected}
                onClick={() => onSelect(row.run_id)}
                style={{
                  width: "100%",
                  padding: 16,
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                  background: "transparent",
                  border: "none",
                  color: "var(--text)",
                  textAlign: "left",
                  cursor: "pointer",
                  font: "inherit",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
                  <div style={{ minWidth: 0 }}>
                    <div className="mono muted" style={{ fontSize: 11 }}>{row.run_id}</div>
                    <div style={{ marginTop: 4, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {strategyLabel}
                    </div>
                  </div>
                  <Pill tone={status.tone} size="xs" pulse={status.pulse} live>{status.label}</Pill>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div>
                    <div className="muted" style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.04em" }}>Sharpe</div>
                    <div className="mono" style={{ marginTop: 4, fontSize: 18, fontWeight: 700 }}>
                      {row.sharpe != null ? row.sharpe.toFixed(2) : "N/A"}
                    </div>
                  </div>
                  <div>
                    <div className="muted" style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.04em" }}>Universe</div>
                    <div className="mono" style={{ marginTop: 6, color: "var(--muted)", fontSize: 12 }}>{row.universe}</div>
                  </div>
                </div>

                <div style={{ minHeight: 28, display: "flex", alignItems: "center" }}>
                  {row.spark && row.spark.length > 0 ? (
                    <SparklineChart
                      points={row.spark}
                      tone={row.return_pct != null && row.return_pct < 0 ? "rose" : "violet"}
                      width={160}
                      height={28}
                      ariaLabel={`Trend for ${row.run_id}`}
                    />
                  ) : (
                    <div
                      aria-label={`Trend placeholder for ${row.run_id}`}
                      style={{
                        width: 160,
                        borderTop: "1px dashed var(--border)",
                      }}
                    />
                  )}
                </div>
              </button>
            </Card>
          </div>
        );
      })}
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
