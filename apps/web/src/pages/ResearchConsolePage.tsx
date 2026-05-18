import { useMemo, useReducer } from "react";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "../components/layout/AppShell";
import { TabSwitcher, type ConsoleTab } from "../components/navigation/TabSwitcher";
import { OverviewTab } from "../features/overview/OverviewTab";
import { BacktestStudioTab } from "../features/backtest/BacktestStudioTab";
import { StrategyCompareTab } from "../features/compare/StrategyCompareTab";
import { RunHistoryTab } from "../features/history/RunHistoryTab";
import { UniverseHealthTab } from "../features/universe/UniverseHealthTab";
import { ReportsExportsTab } from "../features/reports/ReportsExportsTab";
import { fallbackOverview, getOverview } from "../lib/api";
import { qk } from "../lib/qk";

type NavState = { tab: ConsoleTab; prefillRunId?: string };
type NavAction =
  | { type: "SET_TAB"; tab: ConsoleTab }
  | { type: "NAVIGATE"; tab: ConsoleTab; prefillRunId?: string };

function navReducer(state: NavState, action: NavAction): NavState {
  switch (action.type) {
    case "SET_TAB":
      return { tab: action.tab };
    case "NAVIGATE":
      return { tab: action.tab, prefillRunId: action.prefillRunId };
  }
}

const tabLabels: Record<ConsoleTab, string> = {
  overview: "Overview",
  backtest: "Backtest Studio",
  compare: "Strategy Compare",
  history: "Run History",
  universe: "Universe & Data Health",
  reports: "Reports & Exports",
};

export function ResearchConsolePage() {
  const [nav, dispatch] = useReducer(navReducer, { tab: "overview" });
  const apiEnabled = import.meta.env.MODE !== "test";
  const overviewQuery = useQuery({
    queryKey: qk.overview(),
    queryFn: getOverview,
    initialData: fallbackOverview,
    enabled: apiEnabled,
  });
  const overview = useMemo(() => overviewQuery.data ?? fallbackOverview, [overviewQuery.data]);

  const navigate = (tab: ConsoleTab, prefillRunId?: string) => {
    dispatch({ type: "NAVIGATE", tab, prefillRunId });
  };

  const pageTitle = tabLabels[nav.tab];
  const subtitle = getSubtitle(nav.tab);

  return (
    <AppShell
      actions={<TabSwitcher value={nav.tab} onChange={(t) => dispatch({ type: "SET_TAB", tab: t })} />}
    >
      <div className="page-header" style={{ height: "var(--pageheader-h)" }}>
        <div className="page-header-left">
          <h2 className="page-header__title">{pageTitle}</h2>
          <span className="page-header__sub muted">{subtitle}</span>
        </div>
      </div>

      {nav.tab === "overview" && (
        <OverviewTab overview={overview} onNavigate={navigate} />
      )}
      {nav.tab === "backtest" && (
        <BacktestStudioTab prefillRunId={nav.prefillRunId} onNavigate={navigate} />
      )}
      {nav.tab === "compare" && (
        <StrategyCompareTab />
      )}
      {nav.tab === "history" && (
        <RunHistoryTab onNavigate={navigate} />
      )}
      {nav.tab === "universe" && (
        <UniverseHealthTab />
      )}
      {nav.tab === "reports" && (
        <ReportsExportsTab />
      )}
    </AppShell>
  );
}

function getSubtitle(tab: ConsoleTab): string {
  const subs: Record<ConsoleTab, string> = {
    overview: "Champion summary, equity curve, and market regime",
    backtest: "Configure, run, and inspect strategy backtests",
    compare: "Side-by-side performance, risk, and holdings overlap",
    history: "Browse, filter, and re-run past backtests",
    universe: "Top-20 token composition over time + data source status",
    reports: "Generated reports archive + format export center",
  };
  return subs[tab];
}
