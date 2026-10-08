import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card } from "../../components/ui/Card";
import { DemoDataBanner } from "../../components/ui/DemoDataBanner";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { Pill } from "../../components/ui/Pill";
import { Button } from "../../components/ui/Button";
import { Skeleton } from "../../components/ui/Skeleton";
import { UniverseTimeline } from "../../components/universe/UniverseTimeline";
import { DataSourceTile } from "../../components/universe/DataSourceTile";
import { DataAlertRow } from "../../components/universe/DataAlertRow";

import {
  describeApiError,
  fallbackDataAlerts,
  fallbackDataSources,
  fallbackUniverseTimeline,
  getDataAlerts,
  getDataSources,
  getUniverseRefreshStatus,
  getUniverseTimeline,
  refreshUniverse,
} from "../../lib/api";
import { qk } from "../../lib/qk";

type Props = {
  apiEnabled?: boolean;
};

const REFRESH_POLL_MS = 3000;

export function UniverseHealthTab({ apiEnabled: apiEnabledOverride }: Props = {}) {
  const apiEnabled = apiEnabledOverride ?? import.meta.env.MODE !== "test";
  const queryClient = useQueryClient();

  const timeline = useQuery({
    queryKey: qk.universe.timeline(),
    queryFn: getUniverseTimeline,
    initialData: apiEnabled ? undefined : fallbackUniverseTimeline,
    enabled: apiEnabled,
  });

  const sources = useQuery({
    queryKey: qk.universe.sources(),
    queryFn: getDataSources,
    initialData: apiEnabled ? undefined : fallbackDataSources,
    enabled: apiEnabled,
  });

  const alerts = useQuery({
    queryKey: qk.universe.alerts(),
    queryFn: getDataAlerts,
    initialData: apiEnabled ? undefined : fallbackDataAlerts,
    enabled: apiEnabled,
  });

  // POST /universe/refresh only queues a job (202). Invalidating right away
  // refetched the old data, so follow the job and reload once it completes.
  const [refreshRunId, setRefreshRunId] = useState<string | undefined>(undefined);
  const refresh = useMutation({
    mutationFn: refreshUniverse,
    onSuccess: (result) => setRefreshRunId(result.run_id),
  });
  const refreshStatus = useQuery({
    queryKey: qk.universeRefresh(refreshRunId ?? "__none__"),
    queryFn: getUniverseRefreshStatus,
    enabled: apiEnabled && !!refreshRunId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? REFRESH_POLL_MS : false;
    },
  });
  const refreshState = refreshStatus.data?.status;
  useEffect(() => {
    if (refreshState === "completed") void queryClient.invalidateQueries({ queryKey: qk.universe.all() });
  }, [refreshState, queryClient]);

  const tData = timeline.data ?? fallbackUniverseTimeline;
  const sData = sources.data ?? fallbackDataSources;
  const aData = alerts.data ?? fallbackDataAlerts;

  const openAlerts = aData.filter((a) => a.severity !== "emerald").length;
  const isInitialLoading = [timeline, sources, alerts].some((query) => query.isLoading && query.data === undefined);
  const tabFailed = [timeline, sources, alerts].some((query) => (query.isError || query.isRefetchError) && query.data === undefined);
  const isEmpty = tData.tokens.length === 0 && tData.segments.length === 0 && sData.length === 0;
  const retryUniverseQueries = () => {
    void timeline.refetch();
    void sources.refetch();
    void alerts.refetch();
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, padding: 24 }}>
      <DemoDataBanner visible={timeline.data?.data_source === "fallback"} />
      {isInitialLoading ? (
        <UniverseLoadingState />
      ) : tabFailed ? (
        <ErrorBanner message="Unable to load universe data." onRetry={retryUniverseQueries} />
      ) : isEmpty ? (
        <EmptyState title="No universe data available" />
      ) : (
        <>
      {/* ===== Timeline ===== */}
      <Card ariaLabel="Universe composition timeline">
        <SectionHeader
          rightSlot={
            <Button
              variant="outline-violet"
              size="sm"
              loading={refresh.isPending}
              onClick={() => refresh.mutate()}
            >
              ↻ FORCE REFRESH
            </Button>
          }
        >
          UNIVERSE COMPOSITION · LAST 180 DAYS
        </SectionHeader>
        {refresh.isError && (
          <div style={{ marginBottom: 12 }}>
            <ErrorBanner message={describeApiError(refresh.error, "Unable to refresh universe data")} />
          </div>
        )}
        {refreshRunId && (refreshState === "queued" || refreshState === "running") && (
          <p role="status" className="muted" style={{ margin: "0 0 12px", fontSize: 12 }}>
            Refresh {refreshRunId} {refreshState} — data reloads when it completes.
          </p>
        )}
        {refreshRunId && refreshState === "completed" && (
          <p role="status" className="muted" style={{ margin: "0 0 12px", fontSize: 12 }}>
            Universe data refreshed ({refreshRunId})
          </p>
        )}
        {refreshRunId && (refreshState === "failed" || refreshState === "cancelled") && (
          <div style={{ marginBottom: 12 }}>
            <ErrorBanner message={`Universe refresh ${refreshRunId} ${refreshState}.`} />
          </div>
        )}
        <UniverseTimeline data={tData} />
        <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 11, color: "var(--muted)" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span aria-hidden style={{ width: 12, height: 8, background: "var(--gold)", opacity: 0.75, borderRadius: 1 }} />
            <span>Active in top-20</span>
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span aria-hidden style={{ width: 12, height: 8, background: "var(--muted)", opacity: 0.4, borderRadius: 1 }} />
            <span>BTC (benchmark)</span>
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span aria-hidden style={{ width: 1, height: 12, background: "var(--violet)", borderLeft: "1px dashed var(--violet)" }} />
            <span>Major rotation</span>
          </span>
        </div>
      </Card>

      {/* ===== Sources + Alerts 2:1 ===== */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24 }}>
        <Card ariaLabel="Data sources health">
          <SectionHeader>{`DATA SOURCES · ${sData.length} TRACKED`}</SectionHeader>
          <div
            role="list"
            aria-label="Data sources"
            style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}
          >
            {sData.map((s) => (
              <div role="listitem" key={s.id}>
                <DataSourceTile source={s} />
              </div>
            ))}
          </div>
        </Card>

        <Card ariaLabel="Data alerts">
          <SectionHeader
            rightSlot={
              <Pill tone={openAlerts > 0 ? "rose" : "emerald"} size="xs">
                {openAlerts} OPEN
              </Pill>
            }
          >
            DATA ALERTS
          </SectionHeader>
          <div role="list" aria-label="Data alerts list" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {aData.map((a) => (
              <DataAlertRow key={a.id} alert={a} />
            ))}
          </div>
        </Card>
      </div>
        </>
      )}
    </div>
  );
}

function UniverseLoadingState() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 16 }}>
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} data-testid="universe-skeleton">
          <Skeleton variant="card" height={index === 0 ? "320px" : "180px"} />
        </div>
      ))}
    </div>
  );
}
