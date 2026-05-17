import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "../components/layout/AppShell";
import { TabSwitcher, type ConsoleTab } from "../components/navigation/TabSwitcher";
import { DashboardTab } from "../features/dashboard/DashboardTab";
import { OverviewTab } from "../features/overview/OverviewTab";
import { fallbackOverview, getOverview } from "../lib/api";

export function ResearchConsolePage() {
  const [tab, setTab] = useState<ConsoleTab>("overview");
  const apiEnabled = import.meta.env.MODE !== "test";
  const overviewQuery = useQuery({
    queryKey: ["overview"],
    queryFn: getOverview,
    initialData: fallbackOverview,
    enabled: apiEnabled,
  });
  const overview = useMemo(() => overviewQuery.data ?? fallbackOverview, [overviewQuery.data]);

  return (
    <AppShell
      title="Atlas20 Research Console"
      subtitle="Crypto rotation research, champion monitoring, and constrained reruns."
      actions={<TabSwitcher value={tab} onChange={setTab} />}
    >
      {tab === "overview" ? (
        <OverviewTab overview={overview} onOpenDashboard={() => setTab("dashboard")} />
      ) : (
        <DashboardTab overview={overview} />
      )}
    </AppShell>
  );
}
