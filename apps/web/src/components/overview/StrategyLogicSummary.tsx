import { Panel } from "../panels/Panel";

export function StrategyLogicSummary() {
  return (
    <Panel title="Strategy Logic" eyebrow="Rules">
      <div className="logic-grid">
        <div>
          <strong>Universe</strong>
          <span>Top-20 eligible non-stablecoin assets rebuilt point in time.</span>
        </div>
        <div>
          <strong>Leader Selection</strong>
          <span>Momentum rank, 21D return, 42D return, and proximity to highs.</span>
        </div>
        <div>
          <strong>Risk Overlay</strong>
          <span>BTC trailing stop with confirmation and BTC parking during risk-off states.</span>
        </div>
        <div>
          <strong>Cadence</strong>
          <span>14-day rebalance cadence for the current champion preset.</span>
        </div>
      </div>
    </Panel>
  );
}
