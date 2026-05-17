import { Activity, Gauge, ShieldCheck } from "lucide-react";

import type { ChampionSummary } from "../../lib/api";
import { formatMultiple, formatPercent } from "../../lib/format";
import { MetricCard } from "../cards/MetricCard";

export function HeroSummary(props: {
  champion: ChampionSummary;
  onOpenDashboard: () => void;
}) {
  const readableStrategy = props.champion.strategy.replace(/_/g, " ");

  return (
    <section className="hero-summary">
      <div className="hero-summary__copy">
        <div className="status-pill">
          <ShieldCheck size={16} />
          Current champion strategy
        </div>
        <h2>{readableStrategy}</h2>
        <p>
          A constrained momentum-leader rotation that parks risk-off exposure in BTC and
          uses public cached data for reproducible research.
        </p>
        <button className="primary-button" type="button" onClick={props.onOpenDashboard}>
          Open Dashboard
        </button>
      </div>
      <div className="hero-summary__metrics">
        <MetricCard label="Final multiple" value={formatMultiple(props.champion.multiple)} tone="accent" icon={<Activity size={16} />} />
        <MetricCard label="CAGR" value={formatPercent(props.champion.cagr)} tone="positive" icon={<Gauge size={16} />} />
        <MetricCard label="Max drawdown" value={formatPercent(props.champion.max_drawdown)} tone="risk" />
      </div>
    </section>
  );
}
