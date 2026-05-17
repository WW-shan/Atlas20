import type { ChampionSummary, RunStatus } from "../../lib/api";
import { formatMultiple, formatPercent } from "../../lib/format";
import { Panel } from "../panels/Panel";

export function RunStatusRail(props: {
  champion: ChampionSummary;
  run?: RunStatus;
  isRunning: boolean;
}) {
  const summary = props.run?.summary;
  return (
    <aside className="run-rail">
      <Panel title="Run Status" eyebrow="Execution">
        <div className="status-list">
          <div><span>Status</span><strong>{props.isRunning ? "running" : props.run?.status ?? "champion loaded"}</strong></div>
          <div><span>Run ID</span><strong>{props.run?.run_id ?? "champion"}</strong></div>
          <div><span>Multiple</span><strong>{typeof summary?.multiple === "number" ? formatMultiple(summary.multiple) : formatMultiple(props.champion.multiple)}</strong></div>
          <div><span>CAGR</span><strong>{typeof summary?.cagr === "number" ? formatPercent(summary.cagr) : formatPercent(props.champion.cagr)}</strong></div>
        </div>
      </Panel>
    </aside>
  );
}
