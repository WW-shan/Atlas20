import type { HistoryFilter } from "../../lib/api";

type Props = {
  filter: HistoryFilter;
  onChange: (next: HistoryFilter) => void;
  total: number;
};

const CHIPS = ["queued", "running", "completed", "failed", "favorited", "ATLAS", "Momentum", "MeanRev", "Carry"];
const DATE_RANGES: HistoryFilter["dateRange"][] = ["7d", "30d", "90d", "ytd", "all"];

export function Toolbar({ filter, onChange, total }: Props) {
  const toggleChip = (chip: string) => {
    const next = filter.chips.includes(chip)
      ? filter.chips.filter((c) => c !== chip)
      : [...filter.chips, chip];
    onChange({ ...filter, chips: next, page: 1 });
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        padding: 16,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
      }}
      role="search"
      aria-label="Run history filters"
    >
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <input
          type="search"
          value={filter.q}
          onChange={(e) => onChange({ ...filter, q: e.target.value, page: 1 })}
          placeholder="Search by run id, strategy, or universe…"
          aria-label="Search runs"
          className="mono"
          style={{
            flex: 1,
            padding: "8px 12px",
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-input)",
            color: "var(--text)",
            fontSize: 13,
          }}
        />

        <div
          role="tablist"
          aria-label="Date range"
          style={{ display: "flex", gap: 2, border: "1px solid var(--border)", borderRadius: "var(--radius-input)", padding: 2 }}
        >
          {DATE_RANGES.map((r) => {
            const active = filter.dateRange === r;
            return (
              <button
                key={r}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => onChange({ ...filter, dateRange: r, page: 1 })}
                className="mono"
                style={{
                  padding: "4px 10px",
                  fontSize: 11,
                  border: "none",
                  borderRadius: 3,
                  background: active ? "rgba(139,92,246,0.12)" : "transparent",
                  color: active ? "var(--violet)" : "var(--muted)",
                  fontWeight: active ? 700 : 400,
                  cursor: "pointer",
                  textTransform: "uppercase",
                }}
              >
                {r}
              </button>
            );
          })}
        </div>

        <div
          role="group"
          aria-label="View mode"
          style={{ display: "flex", gap: 2, border: "1px solid var(--border)", borderRadius: "var(--radius-input)", padding: 2 }}
        >
          {(["list", "grid"] as const).map((v) => {
            const active = filter.view === v;
            return (
              <button
                key={v}
                type="button"
                aria-pressed={active}
                onClick={() => onChange({ ...filter, view: v })}
                style={{
                  padding: "4px 10px",
                  fontSize: 11,
                  border: "none",
                  borderRadius: 3,
                  background: active ? "var(--border)" : "transparent",
                  color: active ? "var(--text)" : "var(--muted)",
                  fontWeight: active ? 600 : 400,
                  cursor: "pointer",
                  textTransform: "uppercase",
                  fontFamily: "var(--font-sans)",
                  letterSpacing: "0.04em",
                }}
              >
                {v}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div role="group" aria-label="Filter chips" style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {CHIPS.map((chip) => {
            const active = filter.chips.includes(chip);
            return (
              <button
                key={chip}
                type="button"
                aria-pressed={active}
                onClick={() => toggleChip(chip)}
                style={{
                  padding: "4px 10px",
                  fontSize: 11,
                  borderRadius: "var(--radius-pill)",
                  border: `1px solid ${active ? "var(--violet)" : "var(--border)"}`,
                  background: active ? "rgba(139,92,246,0.10)" : "transparent",
                  color: active ? "var(--violet)" : "var(--muted)",
                  cursor: "pointer",
                  fontFamily: "var(--font-sans)",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  fontWeight: 600,
                }}
              >
                {chip}
              </button>
            );
          })}
        </div>
        <span className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
          <span className="mono">{total.toLocaleString()}</span> runs
        </span>
      </div>
    </div>
  );
}
