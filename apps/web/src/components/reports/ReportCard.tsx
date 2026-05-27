import type { ReportEntry } from "../../lib/api";
import { Card } from "../ui/Card";
import { Pill } from "../ui/Pill";
import { ReportThumbnail } from "./ReportThumbnail";

type Props = {
  entry: ReportEntry;
  onDownload: (id: string) => void;
  downloadBusy?: boolean;
  downloadsDisabled?: boolean;
};

function formatBytes(n: number): string {
  if (n === 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

const reportTypeTone: Record<ReportEntry["report_type"], "cyan" | "violet" | "muted" | "emerald"> = {
  weekly:   "cyan",
  run:      "violet",
  compare:  "violet",
  universe: "emerald",
};

export function ReportCard({ entry, onDownload, downloadBusy, downloadsDisabled }: Props) {
  const isGenerating = entry.status === "generating";
  const downloadDisabled = Boolean(isGenerating || downloadBusy || downloadsDisabled);
  return (
    <Card
      variant="report"
      ariaLabel={`Report ${entry.title}`}
      thumbnail={<ReportThumbnail kind={entry.thumbnail} />}
      style={
        entry.highlight
          ? { boxShadow: "0 0 0 1px rgba(245,158,11,0.40), 0 0 24px rgba(245,158,11,0.18)" }
          : undefined
      }
    >
      <div data-report-id={entry.id} data-highlight={entry.highlight ? "true" : undefined}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <Pill tone={reportTypeTone[entry.report_type]} size="xs">
            {entry.report_type}
          </Pill>
          {entry.highlight && <Pill tone="gold-outline" size="xs">FEATURED</Pill>}
          {isGenerating && <Pill tone="cyan" size="xs" pulse>GENERATING</Pill>}
        </div>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "var(--text)" }}>
          {entry.title}
        </h3>
        <span className="mono muted" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
          {entry.subtitle}
        </span>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: 12,
            fontSize: 11,
          }}
        >
          <span className="mono muted">
            {formatBytes(entry.size_bytes)} · {entry.generated_at.slice(0, 10)}
          </span>
          <button
            type="button"
            aria-label={`Download ${entry.title}`}
            aria-busy={downloadBusy ? "true" : undefined}
            onClick={() => {
              if (!downloadDisabled) void onDownload(entry.id);
            }}
            disabled={downloadDisabled}
            style={{
              background: "transparent",
              border: "none",
              color: downloadDisabled ? "var(--muted)" : "var(--gold)",
              fontSize: 11,
              fontFamily: "var(--font-sans)",
              fontWeight: 600,
              letterSpacing: "0.06em",
              cursor: downloadDisabled ? "not-allowed" : "pointer",
              opacity: downloadDisabled ? 0.5 : 1,
              padding: 0,
              textTransform: "uppercase",
            }}
          >
            {isGenerating ? "GENERATING..." : "DOWNLOAD"}
          </button>
        </div>
      </div>
    </Card>
  );
}
