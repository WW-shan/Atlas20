import type { BacktestConfig } from "../../lib/api";
import { SectionHeader } from "../ui/SectionHeader";
import { Button } from "../ui/Button";

type Props = {
  value: BacktestConfig;
  onChange: (next: BacktestConfig) => void;
  onRun: () => void;
  isRunning: boolean;
  refreshing?: boolean;
  presets?: { slug: string; display_name: string }[];
};

function clamp(n: number, lo: number, hi: number): number {
  if (Number.isNaN(n)) return lo;
  return Math.min(hi, Math.max(lo, n));
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  height: 32,
  padding: "0 10px",
  fontSize: 12,
  color: "var(--text)",
  background: "var(--bg)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-input)",
};

const FALLBACK_PRESETS = [
  { slug: "base", display_name: "Base Config" },
  { slug: "five_year_2020_2024", display_name: "Five Year 2020 2024" },
  { slug: "five_year_exact_2021_04_22_2026_04_22", display_name: "Five Year Exact 2021 04 22 2026 04 22" },
  { slug: "bear_bottom_to_current_2022_11_21_2026_04_22", display_name: "Bear Bottom To Current 2022 11 21 2026 04 22" },
];

export function ParameterSidebar({ value, onChange, onRun, isRunning, refreshing, presets }: Props) {
  const options = presets && presets.length > 0 ? presets : FALLBACK_PRESETS;
  const fullList = options.some((p) => p.slug === value.preset) ? options : [{ slug: value.preset, display_name: value.preset }, ...options];
  return (
    <aside
      style={{
        width: 340,
        flex: "0 0 340px",
        padding: 20,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        display: "flex",
        flexDirection: "column",
        gap: 24,
      }}
      aria-label="Backtest parameters"
    >
      <div>
        <SectionHeader rightSlot={refreshing ? <RefreshingBadge /> : undefined}>STRATEGY</SectionHeader>
        <select
          value={value.preset}
          onChange={(e) => onChange({ ...value, preset: e.target.value })}
          style={inputStyle}
          aria-label="Strategy preset"
        >
          {fullList.map((p) => (
            <option key={p.slug} value={p.slug}>{p.display_name}</option>
          ))}
        </select>
      </div>

      <div>
        <SectionHeader>UNIVERSE</SectionHeader>
        <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>
          Top-N
          <span className="mono" style={{ color: "var(--text)" }}>N = {value.universe.topN}</span>
        </label>
        <input
          type="range"
          min={5}
          max={50}
          value={value.universe.topN}
          onChange={(e) => onChange({ ...value, universe: { ...value.universe, topN: Number(e.target.value) } })}
          aria-label="Top-N universe size"
          style={{ width: "100%", accentColor: "var(--violet)" }}
        />
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginTop: 12 }}>
          <input
            type="checkbox"
            checked={value.universe.excludeStable}
            onChange={(e) => onChange({ ...value, universe: { ...value.universe, excludeStable: e.target.checked } })}
            style={{ width: 14, height: 14, accentColor: "var(--violet)" }}
          />
          Exclude stablecoins
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginTop: 8 }}>
          <input
            type="checkbox"
            checked={value.universe.excludeWrapped}
            onChange={(e) => onChange({ ...value, universe: { ...value.universe, excludeWrapped: e.target.checked } })}
            style={{ width: 14, height: 14, accentColor: "var(--violet)" }}
          />
          Exclude wrapped tokens
        </label>
      </div>

      <div>
        <SectionHeader>WINDOW</SectionHeader>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
          <input
            type="date"
            value={value.window.start}
            onChange={(e) => onChange({ ...value, window: { ...value.window, start: e.target.value } })}
            aria-label="Window start"
            style={inputStyle}
          />
          <input
            type="date"
            value={value.window.end}
            onChange={(e) => onChange({ ...value, window: { ...value.window, end: e.target.value } })}
            aria-label="Window end"
            style={inputStyle}
          />
        </div>
        <select
          value={value.window.rebalance}
          onChange={(e) => onChange({ ...value, window: { ...value.window, rebalance: e.target.value as BacktestConfig["window"]["rebalance"] } })}
          style={inputStyle}
          aria-label="Rebalance frequency"
        >
          <option value="Weekly">Weekly (Mon 00:00 UTC)</option>
          <option value="Biweekly">Biweekly</option>
          <option value="Monthly">Monthly</option>
        </select>
      </div>

      <div>
        <SectionHeader>ALLOCATION</SectionHeader>
        <label style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>
          Position size
          <span className="mono" style={{ color: "var(--text)" }}>{value.allocation.positionPct.toFixed(1)}% per slot</span>
        </label>
        <input
          type="range"
          min={1}
          max={20}
          step={0.5}
          value={value.allocation.positionPct}
          onChange={(e) => onChange({ ...value, allocation: { ...value.allocation, positionPct: Number(e.target.value) } })}
          aria-label="Position size percent"
          style={{ width: "100%", accentColor: "var(--violet)" }}
        />
        <label style={{ display: "block", fontSize: 12, color: "var(--muted)", marginTop: 12 }}>
          Slots
          <input
            type="number"
            min={1}
            max={50}
            value={value.allocation.slots}
            onChange={(e) => onChange({ ...value, allocation: { ...value.allocation, slots: clamp(Number(e.target.value), 1, 50) } })}
            style={{ ...inputStyle, marginTop: 6 }}
          />
        </label>
      </div>

      <div>
        <SectionHeader>COSTS</SectionHeader>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <label style={{ display: "block", fontSize: 12, color: "var(--muted)" }}>
            Fee bps
            <input
              type="number"
              min={0}
              max={500}
              value={value.costs.feeBps}
              onChange={(e) => onChange({ ...value, costs: { ...value.costs, feeBps: clamp(Number(e.target.value), 0, 500) } })}
              style={{ ...inputStyle, marginTop: 6 }}
              aria-label="Fee basis points"
            />
          </label>
          <label style={{ display: "block", fontSize: 12, color: "var(--muted)" }}>
            Slippage bps
            <input
              type="number"
              min={0}
              max={500}
              value={value.costs.slippageBps}
              onChange={(e) => onChange({ ...value, costs: { ...value.costs, slippageBps: clamp(Number(e.target.value), 0, 500) } })}
              style={{ ...inputStyle, marginTop: 6 }}
              aria-label="Slippage basis points"
            />
          </label>
        </div>
      </div>

      <Button variant="gold" size="lg" loading={isRunning} onClick={onRun}>
        ▶ RUN BACKTEST
      </Button>
    </aside>
  );
}

function RefreshingBadge() {
  return (
    <span
      data-testid="parameter-sidebar-refreshing"
      role="status"
      aria-label="Refreshing backtest parameters"
      className="mono"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        borderRadius: "var(--radius-pill)",
        border: "1px solid rgba(6,182,212,0.30)",
        background: "rgba(6,182,212,0.08)",
        color: "var(--cyan)",
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.04em",
        padding: "2px 8px",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          border: "1px solid rgba(6,182,212,0.30)",
          borderTopColor: "var(--cyan)",
          animation: "spin 0.8s linear infinite",
        }}
      />
      REFRESHING
    </span>
  );
}
