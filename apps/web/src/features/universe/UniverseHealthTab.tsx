import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card } from "../../components/ui/Card";
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
  fallbackDataAlerts,
  fallbackDataSources,
  fallbackUniverseTimeline,
  getDataAlerts,
  getDataSources,
  getUniverseTimeline,
  refreshUniverse,
} from "../../lib/api";
import { qk } from "../../lib/qk";

type Props = {
  apiEnabled?: boolean;
};

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

  const refresh = useMutation({
    mutationFn: refreshUniverse,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.universe.all() });
    },
  });

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
