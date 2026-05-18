import type { DataAlert } from "../../lib/api";

type Props = {
  alert: DataAlert;
};

const toneColors: Record<DataAlert["severity"], string> = {
  rose:    "var(--rose)",
  cyan:    "var(--cyan)",
  emerald: "var(--emerald)",
};

function AlertIcon({ kind, color }: { kind: DataAlert["icon"]; color: string }) {
  if (kind === "alert-triangle") {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden focusable="false">
        <path d="M8 1.5 L15 14 L1 14 Z" fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
        <line x1="8" y1="6"  x2="8" y2="10" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="8" cy="12" r="0.8" fill={color} />
      </svg>
    );
  }
  if (kind === "check-circle") {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden focusable="false">
        <circle cx="8" cy="8" r="6.5" fill="none" stroke={color} strokeWidth="1.5" />
        <polyline points="5,8 7.5,10.5 11,6" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  // info
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden focusable="false">
      <circle cx="8" cy="8" r="6.5" fill="none" stroke={color} strokeWidth="1.5" />
      <circle cx="8" cy="5" r="0.9" fill={color} />
      <line x1="8" y1="7.5" x2="8" y2="11.5" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function formatRelative(iso: string, now = Date.now()): string {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const diff = Math.max(0, now - ts);
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function DataAlertRow({ alert }: Props) {
  const color = toneColors[alert.severity];
  return (
    <div
      role="listitem"
      data-alert-id={alert.id}
      data-severity={alert.severity}
      data-icon={alert.icon}
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto",
        gap: 12,
        alignItems: "center",
        padding: "10px 14px",
        background: "var(--surface)",
        borderTop: "1px solid var(--border)",
        borderRight: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
        borderLeft: `3px solid ${color}`,
        borderRadius: "var(--radius-card)",
      }}
    >
      <AlertIcon kind={alert.icon} color={color} />
      <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
        <span style={{ fontSize: 13, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis" }}>
          {alert.title}
        </span>
        <span className="mono" style={{ fontSize: 11, color: "var(--muted)" }}>
          {alert.meta}
        </span>
      </div>
      <span className="mono" style={{ fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap" }}>
        {formatRelative(alert.ts)}
      </span>
    </div>
  );
}
