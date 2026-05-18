import type { OverviewPayload } from "../../lib/api";
import type { ConsoleTab } from "../../components/navigation/TabSwitcher";
import { formatCurrencyCompact, formatPercent } from "../../lib/format";
import { Panel } from "../../components/panels/Panel";
import { MetricCard } from "../../components/cards/MetricCard";
import { HeroSummary } from "../../components/overview/HeroSummary";
import { StrategyLogicSummary } from "../../components/overview/StrategyLogicSummary";
import { TopStrategiesTable } from "../../components/overview/TopStrategiesTable";
import { SparklineChart } from "../../components/charts/SparklineChart";

export function OverviewTab(props: {
  overview: OverviewPayload;
  onNavigate: (tab: ConsoleTab, prefillRunId?: string) => void;
}) {
  return (
    <div className="overview-layout">
      <HeroSummary champion={props.overview.champion} onOpenDashboard={() => props.onNavigate("backtest")} />
      <div className="metric-grid">
        <MetricCard label="Sharpe" value={props.overview.champion.sharpe.toFixed(2)} />
        <MetricCard label="Monthly win rate" value={formatPercent(props.overview.champion.monthly_win_rate)} tone="positive" />
        <MetricCard label="Annualized turnover" value={props.overview.champion.annualized_turnover.toFixed(1)} />
        <MetricCard label="Ending equity" value={formatCurrencyCompact(props.overview.champion.ending_equity)} tone="accent" />
      </div>
      <div className="overview-grid">
        <Panel title="Champion Equity Curve" eyebrow="Performance" className="panel--wide">
          <SparklineChart points={props.overview.equity_curve} />
        </Panel>
        <StrategyLogicSummary />
      </div>
      <Panel title="Top Strategy Ranking" eyebrow="Comparators">
        <TopStrategiesTable rows={props.overview.top_strategies} />
      </Panel>
    </div>
  );
}
