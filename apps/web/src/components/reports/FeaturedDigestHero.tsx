import type { FeaturedDigest, ReportEntry } from "../../lib/api";
import { Card } from "../ui/Card";
import { Pill } from "../ui/Pill";

type ReportTypeFilter = "all" | ReportEntry["report_type"];

type Props = {
  digest: FeaturedDigest;
  activeFilter: ReportTypeFilter;
  onFilterChange: (filter: ReportTypeFilter) => void;
};

const FILTER_OPTIONS: { key: ReportTypeFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "weekly", label: "Weekly" },
  { key: "run", label: "Run" },
  { key: "compare", label: "Compare" },
  { key: "universe", label: "Universe" },
];

export function FeaturedDigestHero({
  digest,
  activeFilter,
  onFilterChange,
}: Props) {
  return (
    <Card variant="hero" ariaLabel="Featured digest hero">
      <div style={{ display: "flex", flexWrap: "wrap", gap: 24, alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0, alignItems: "flex-start" }}>
          <Pill tone="gold-outline" size="xs">FEATURED DIGEST</Pill>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em" }}>
            {digest.title}
          </h2>
          <span className="muted" style={{ fontSize: 13 }}>
            {digest.subtitle}
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end", minWidth: 0 }}>
          <div
            role="tablist"
            aria-label="Report type filter"
            style={{ display: "flex", gap: 4, flexWrap: "wrap", justifyContent: "flex-end" }}
          >
            {FILTER_OPTIONS.map((opt) => {
              const active = opt.key === activeFilter;
              return (
                <button
                  key={opt.key}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  data-filter={opt.key}
                  onClick={() => onFilterChange(opt.key)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "var(--radius-pill)",
                    border: `1px solid ${active ? "var(--violet)" : "var(--border)"}`,
                    background: active ? "rgba(139,92,246,0.10)" : "transparent",
                    color: active ? "var(--violet)" : "var(--muted)",
                    fontSize: 12,
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                    cursor: "pointer",
                    fontFamily: "var(--font-sans)",
                  }}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
          <span className="mono muted" style={{ fontSize: 11 }}>
            Generated {digest.generated_at.slice(0, 10)}
          </span>
        </div>
      </div>
    </Card>
  );
}
