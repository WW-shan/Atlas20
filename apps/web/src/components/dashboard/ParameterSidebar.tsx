import type { DashboardFormState } from "../../features/dashboard/useChampionPreset";

export function ParameterSidebar(props: {
  value: DashboardFormState;
  onChange: (value: DashboardFormState) => void;
  onResetChampion: () => void;
  onRun: () => void;
  isRunning: boolean;
}) {
  const update = (patch: Partial<DashboardFormState>) => props.onChange({ ...props.value, ...patch });
  return (
    <aside className="sidebar">
      <div className="sidebar__header">
        <span>Parameters</span>
        <button type="button" onClick={props.onResetChampion}>Reset</button>
      </div>
      <label>
        Start
        <input value={props.value.window.start_date} onChange={(event) => update({ window: { ...props.value.window, start_date: event.target.value } })} />
      </label>
      <label>
        End
        <input value={props.value.window.end_date} onChange={(event) => update({ window: { ...props.value.window, end_date: event.target.value } })} />
      </label>
      <label>
        Frequency
        <select value={props.value.strategy.frequency} onChange={(event) => update({ strategy: { ...props.value.strategy, frequency: event.target.value } })}>
          <option value="7D">7D</option>
          <option value="14D">14D</option>
        </select>
      </label>
      <label>
        Top N
        <input type="number" min={1} max={3} value={props.value.strategy.top_n} onChange={(event) => update({ strategy: { ...props.value.strategy, top_n: Number(event.target.value) } })} />
      </label>
      <label>
        Risk Mode
        <select value={props.value.risk.mode} onChange={(event) => update({ risk: { ...props.value.risk, mode: event.target.value } })}>
          <option value="always_on">Always On</option>
          <option value="bull_only">Bull Only</option>
        </select>
      </label>
      <label>
        BTC Stop Lookback
        <input type="number" min={0} value={props.value.risk.stop_lookback_days} onChange={(event) => update({ risk: { ...props.value.risk, stop_lookback_days: Number(event.target.value) } })} />
      </label>
      <button className="primary-button primary-button--full" type="button" onClick={props.onRun} disabled={props.isRunning}>
        {props.isRunning ? "Running..." : "Run Backtest"}
      </button>
    </aside>
  );
}
