import type { CSSProperties, ReactNode } from "react";

import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { SectionHeader } from "../../components/ui/SectionHeader";
import type { BacktestConfig, OptionsPayload } from "../../lib/api";

type Props = {
  options: OptionsPayload;
  selectedPresets: string[];
  selectedTopNs: number[];
  selectedRebalances: BacktestConfig["window"]["rebalance"][];
  runCount: number;
  pending: boolean;
  disabled: boolean;
  onTogglePreset: (slug: string) => void;
  onToggleTopN: (topN: number) => void;
  onToggleRebalance: (rebalance: BacktestConfig["window"]["rebalance"]) => void;
  onSubmit: () => void;
};

export function StrategyLabControls({
  options,
  selectedPresets,
  selectedTopNs,
  selectedRebalances,
  runCount,
  pending,
  disabled,
  onTogglePreset,
  onToggleTopN,
  onToggleRebalance,
  onSubmit,
}: Props) {
  return (
    <Card ariaLabel="Strategy Lab experiment matrix">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <SectionHeader>Experiment matrix</SectionHeader>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="mono" style={{ color: "var(--text)", fontSize: 13 }}>
            {runCount} runs selected
          </span>
          <Button variant="gold" loading={pending} disabled={disabled || pending} onClick={onSubmit}>
            Queue experiment
          </Button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 0.9fr 1fr", gap: 18, marginTop: 14 }}>
        <ControlGroup label="Presets">
          {options.presets.map((preset) => (
            <label key={preset.slug} style={optionStyle}>
              <input
                type="checkbox"
                checked={selectedPresets.includes(preset.slug)}
                onChange={() => onTogglePreset(preset.slug)}
              />
              <span>{preset.display_name}</span>
            </label>
          ))}
        </ControlGroup>

        <ControlGroup label="Universe">
          {options.universes
            .filter((universe) => universe.topN >= 10)
            .map((universe) => (
              <label key={universe.topN} style={optionStyle}>
                <input
                  type="checkbox"
                  checked={selectedTopNs.includes(universe.topN)}
                  onChange={() => onToggleTopN(universe.topN)}
                />
                <span>{universe.label}</span>
              </label>
            ))}
        </ControlGroup>

        <ControlGroup label="Rebalance">
          {options.rebalances.map((rebalance) => (
            <label key={rebalance.value} style={optionStyle}>
              <input
                type="checkbox"
                checked={selectedRebalances.includes(rebalance.value)}
                onChange={() => onToggleRebalance(rebalance.value)}
              />
              <span>{rebalance.label}</span>
            </label>
          ))}
        </ControlGroup>
      </div>
    </Card>
  );
}

function ControlGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 8 }}>
        {label}
      </legend>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>{children}</div>
    </fieldset>
  );
}

const optionStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  minHeight: 28,
  color: "var(--text)",
  fontSize: 13,
};
