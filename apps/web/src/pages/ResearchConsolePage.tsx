import { useReducer } from "react";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "../components/layout/AppShell";
import { TabSwitcher, type ConsoleTab } from "../components/navigation/TabSwitcher";
import { OverviewTab } from "../features/overview/OverviewTab";
import { BacktestStudioTab } from "../features/backtest/BacktestStudioTab";
import { StrategyCompareTab } from "../features/compare/StrategyCompareTab";
import { RunHistoryTab } from "../features/history/RunHistoryTab";
import { UniverseHealthTab } from "../features/universe/UniverseHealthTab";
import { ReportsExportsTab } from "../features/reports/ReportsExportsTab";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { ErrorBoundary } from "../components/ui/ErrorBoundary";
import { Pill } from "../components/ui/Pill";
import { Skeleton } from "../components/ui/Skeleton";
import { getOverview } from "../lib/api";
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
  const overviewQuery = useQuery({
    queryKey: qk.overview(),
    queryFn: getOverview,
  });

  const navigate = (tab: ConsoleTab, prefillRunId?: string) => {
    dispatch({ type: "NAVIGATE", tab, prefillRunId });
  };

  const pageTitle = tabLabels[nav.tab];
  const subtitle = getSubtitle(nav.tab);
  const overviewData = overviewQuery.data;
  const overviewFailed = overviewQuery.isError || overviewQuery.isRefetchError;
  const showOverviewStale = nav.tab === "overview" && overviewFailed && overviewData !== undefined;

  return (
    <>
      <a href="#main-content" className="skip-link">Skip to content</a>
      <AppShell
        actions={<TabSwitcher value={nav.tab} onChange={(t) => dispatch({ type: "SET_TAB", tab: t })} />}
      >
        <main id="main-content">
      <div className="page-header" style={{ minHeight: "var(--pageheader-h)" }}>
        <div className="page-header-left">
          <h2 className="page-header__title">{pageTitle}</h2>
          <span className="page-header__sub muted">{subtitle}</span>
        </div>
        {showOverviewStale && (
          <button
            type="button"
            data-testid="overview-stale-indicator"
            aria-live="polite"
            onClick={() => { void overviewQuery.refetch(); }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              background: "transparent",
              border: 0,
              padding: 0,
            }}
          >
            <Pill tone="rose" size="xs">stale — refresh failed</Pill>
          </button>
        )}
      </div>

      {nav.tab === "overview" && overviewQuery.isLoading && overviewData === undefined && <PageSkeleton />}
      {nav.tab === "overview" && overviewFailed && overviewData === undefined && (
        <div style={{ padding: 24 }}>
          <ErrorBanner
            message="Unable to load overview."
            onRetry={() => { void overviewQuery.refetch(); }}
          />
        </div>
      )}
      {nav.tab === "overview" && overviewData && (
        <ErrorBoundary>
          <OverviewTab overview={overviewData} onNavigate={navigate} />
        </ErrorBoundary>
      )}
      {nav.tab === "backtest" && (
        <ErrorBoundary>
          <BacktestStudioTab prefillRunId={nav.prefillRunId} onNavigate={navigate} />
        </ErrorBoundary>
      )}
      {nav.tab === "compare" && (
        <ErrorBoundary>
          <StrategyCompareTab />
        </ErrorBoundary>
      )}
      {nav.tab === "history" && (
        <ErrorBoundary>
          <RunHistoryTab onNavigate={navigate} />
        </ErrorBoundary>
      )}
      {nav.tab === "universe" && (
        <ErrorBoundary>
          <UniverseHealthTab />
        </ErrorBoundary>
      )}
      {nav.tab === "reports" && (
        <ErrorBoundary>
          <ReportsExportsTab />
        </ErrorBoundary>
      )}
        </main>
      </AppShell>
    </>
  );
}

function PageSkeleton() {
  return (
    <div
      data-testid="page-skeleton"
      style={{
        minHeight: "55vh",
        padding: 24,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Skeleton variant="card" width="min(720px, 100%)" height="260px" />
    </div>
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
