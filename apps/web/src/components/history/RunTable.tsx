import type { RunRow } from "../../lib/api";
import type { RunStatusEnum } from "../ui/types";
import { Pill } from "../ui/Pill";
import { SparklineChart } from "../charts/SparklineChart";

type Props = {
  rows: RunRow[];
  selectedId?: string;
  onSelect: (runId: string) => void;
  onToggleFavorite?: (runId: string) => void;
};

function statusTone(status: RunStatusEnum): { tone: "muted" | "cyan" | "emerald" | "rose"; pulse: boolean } {
  switch (status) {
    case "queued":    return { tone: "muted",   pulse: false };
    case "running":   return { tone: "cyan",    pulse: true };
    case "completed": return { tone: "emerald", pulse: false };
    case "failed":    return { tone: "rose",    pulse: false };
  }
}

function formatPct(v: number | undefined, digits = 2): string {
  if (v === undefined) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(digits)}%`;
}

function formatDuration(s: number | undefined): string {
  if (s === undefined) return "—";
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}m ${sec}s`;
}

function formatDate(iso: string): string {
  return iso.slice(0, 10);
}

const COLS: { key: string; label: string }[] = [
  { key: "selected", label: "" },
  { key: "favorite", label: "" },
  { key: "run_id",   label: "RUN ID" },
  { key: "family",   label: "FAMILY" },
  { key: "strategy", label: "STRATEGY" },
  { key: "universe", label: "UNIVERSE" },
  { key: "window",   label: "WINDOW" },
  { key: "status",   label: "STATUS" },
  { key: "return",   label: "RETURN" },
  { key: "sharpe",   label: "SHARPE" },
  { key: "max_dd",   label: "MAX DD" },
  { key: "duration", label: "TIME" },
  { key: "spark",    label: "TREND" },
  { key: "created",  label: "CREATED" },
];

export function RunTable({ rows, selectedId, onSelect, onToggleFavorite }: Props) {
  return (
    <div
      role="region"
      aria-label="Run history table"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
        overflowX: "auto",
      }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }} aria-label="Runs list">
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {COLS.map((c) => (
              <th
                key={c.key}
                scope="col"
                style={{
                  textAlign: "left",
                  padding: "10px 12px",
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                  whiteSpace: "nowrap",
                }}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const status = statusTone(r.status);
            const isSelected = r.run_id === selectedId;
            return (
              <tr
                key={r.run_id}
                data-run-id={r.run_id}
                data-selected={isSelected ? "true" : undefined}
                role="row"
                aria-selected={isSelected}
                tabIndex={0}
                style={{ borderBottom: "1px solid var(--border)", cursor: "pointer" }}
                onClick={() => onSelect(r.run_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(r.run_id);
                  }
                }}
              >
                <td style={{ padding: 0, width: 4 }}>
                  <div
                    aria-hidden
                    style={{
                      width: 3,
                      height: 30,
                      background: isSelected ? "var(--gold)" : "transparent",
                      borderRadius: 2,
                    }}
                  />
                </td>
                <td style={{ padding: "8px 12px", width: 28 }}>
                  <button
                    type="button"
                    aria-label={r.favorited ? `Unfavorite ${r.run_id}` : `Favorite ${r.run_id}`}
                    aria-pressed={r.favorited ?? false}
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleFavorite?.(r.run_id);
                    }}
                    style={{
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      fontSize: 14,
                      color: r.favorited ? "var(--gold)" : "var(--muted)",
                      padding: 0,
                    }}
                  >
                    {r.favorited ? "★" : "☆"}
                  </button>
                </td>
                <td className="mono" style={{ padding: "8px 12px", whiteSpace: "nowrap" }}>{r.run_id}</td>
                <td className="mono" style={{ padding: "8px 12px", color: "var(--muted)", whiteSpace: "nowrap" }}>
                  {r.strategy_family ?? "—"}
                </td>
                <td style={{ padding: "8px 12px", whiteSpace: "nowrap" }}>{r.strategy}</td>
                <td className="mono" style={{ padding: "8px 12px", color: "var(--muted)", whiteSpace: "nowrap" }}>{r.universe}</td>
                <td className="mono" style={{ padding: "8px 12px", color: "var(--muted)", fontSize: 11, whiteSpace: "nowrap" }}>
                  {formatDate(r.window.start)} → {formatDate(r.window.end)}
                </td>
                <td style={{ padding: "8px 12px" }}>
                  <Pill tone={status.tone} size="xs" pulse={status.pulse}>{r.status}</Pill>
                </td>
                <td
                  className="mono"
                  data-metric="return"
                  style={{
                    padding: "8px 12px",
                    textAlign: "right",
                    color: r.return_pct === undefined ? "var(--muted)" : r.return_pct >= 0 ? "var(--emerald)" : "var(--rose)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {formatPct(r.return_pct)}
                </td>
                <td className="mono" style={{ padding: "8px 12px", textAlign: "right", whiteSpace: "nowrap" }}>
                  {r.sharpe !== undefined ? r.sharpe.toFixed(2) : "—"}
                </td>
                <td
                  className="mono"
                  style={{
                    padding: "8px 12px",
                    textAlign: "right",
                    color: r.max_dd === undefined ? "var(--muted)" : "var(--rose)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {formatPct(r.max_dd)}
                </td>
                <td className="mono" style={{ padding: "8px 12px", color: "var(--muted)", whiteSpace: "nowrap" }}>
                  {formatDuration(r.duration_s)}
                </td>
                <td style={{ padding: "8px 12px" }}>
                  {r.spark && r.spark.length > 0 ? (
                    <SparklineChart
                      points={r.spark}
                      tone={r.return_pct !== undefined && r.return_pct < 0 ? "rose" : "violet"}
                      width={80}
                      height={20}
                      ariaLabel={`Trend for ${r.run_id}`}
                    />
                  ) : (
                    <span className="muted" style={{ fontSize: 11 }}>—</span>
                  )}
                </td>
                <td className="mono" style={{ padding: "8px 12px", color: "var(--muted)", fontSize: 11, whiteSpace: "nowrap" }}>
                  {formatDate(r.created_at)}
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={COLS.length} style={{ padding: 32, textAlign: "center" }} className="muted">
                No runs match these filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
