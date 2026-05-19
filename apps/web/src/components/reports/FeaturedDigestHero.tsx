import type { FeaturedDigest, ReportFormat } from "../../lib/api";
import { Card } from "../ui/Card";
import { Pill } from "../ui/Pill";
import { Button } from "../ui/Button";

type Props = {
  digest: FeaturedDigest;
  selectedFormat: ReportFormat;
  onSelectFormat: (fmt: ReportFormat) => void;
  onDownloadAll: () => void;
  downloadLoading?: boolean;
};

export function FeaturedDigestHero({ digest, selectedFormat, onSelectFormat, onDownloadAll, downloadLoading }: Props) {
  return (
    <Card variant="hero" ariaLabel="Featured digest hero">
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 24, alignItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Pill tone="gold-outline" size="xs">FEATURED DIGEST</Pill>
          <h2 style={{ margin: 0, fontSize: 26, fontWeight: 600, letterSpacing: "-0.01em" }}>
            {digest.title}
          </h2>
          <span className="muted" style={{ fontSize: 13 }}>
            {digest.subtitle}
          </span>
          <div
            role="group"
            aria-label="Digest format"
            style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}
          >
            {digest.formats.map((fmt) => {
              const active = fmt === selectedFormat;
              return (
                <button
                  key={fmt}
                  type="button"
                  aria-pressed={active}
                  data-format={fmt}
                  onClick={() => onSelectFormat(fmt)}
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
                  {fmt}
                </button>
              );
            })}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
          <Button variant="gold" loading={downloadLoading} onClick={onDownloadAll}>↓ DOWNLOAD ALL · BUNDLE</Button>
          <span className="mono muted" style={{ fontSize: 11 }}>
            Generated {digest.generated_at.slice(0, 10)}
          </span>
        </div>
      </div>
    </Card>
  );
}
