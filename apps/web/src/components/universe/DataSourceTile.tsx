import type { DataSource } from "../../lib/api";
import { Pill } from "../ui/Pill";

type Props = {
  source: DataSource;
};

const toneByStatus: Record<DataSource["status"], { color: string; pill: "emerald" | "cyan" | "rose" }> = {
  healthy:  { color: "var(--emerald)", pill: "emerald" },
  degraded: { color: "var(--cyan)",    pill: "cyan" },
  error:    { color: "var(--rose)",    pill: "rose" },
};

function formatLastSync(s: number): string {
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function DataSourceTile({ source }: Props) {
  const tone = toneByStatus[source.status];
  return (
    <div
      data-source-id={source.id}
      data-status={source.status}
      aria-label={`Data source ${source.name}, status ${source.status}`}
      style={{
        position: "relative",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        padding: "12px 14px 12px 18px",
        overflow: "hidden",
      }}
    >
      <span
        aria-hidden
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: 3,
          background: tone.color,
        }}
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
          {source.name}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Pill tone={tone.pill} size="xs">{source.status}</Pill>
          <span className="mono muted" style={{ fontSize: 11 }}>
            Last sync · {formatLastSync(source.last_sync_seconds)}
          </span>
        </div>
      </div>
    </div>
  );
}
