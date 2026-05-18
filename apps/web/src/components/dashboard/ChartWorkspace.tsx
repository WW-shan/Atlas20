import type { OverviewPayload } from "../../lib/api";
import { SparklineChart } from "../charts/SparklineChart";
import { Panel } from "../panels/Panel";
import { SelectionHistoryTable } from "./SelectionHistoryTable";

export function ChartWorkspace(props: { overview: OverviewPayload }) {
  return (
    <div className="workspace">
      <Panel title="Equity" eyebrow="Chart">
        <SparklineChart points={props.overview.equity_curve.map((p) => p.value)} tone="gold" height={48} width={400} ariaLabel="Champion equity curve" />
      </Panel>
      <Panel title="Recent Selection History" eyebrow="Rebalances">
        <SelectionHistoryTable rows={props.overview.selection_history.slice(-8)} />
      </Panel>
    </div>
  );
}
