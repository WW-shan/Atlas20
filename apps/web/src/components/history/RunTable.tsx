import type { CSSProperties } from "react";

import type { RunRow } from "../../lib/api";
import type { RunStatusEnum } from "../ui/types";
import { Pill } from "../ui/Pill";
import { SparklineChart } from "../charts/SparklineChart";

type Props = {
  rows: RunRow[];
  selectedId?: string;
  onSelect: (runId: string) => void;
  onToggleFavorite?: (runId: string) => void;
  favoriteBusyId?: string;
  favoritesDisabled?: boolean;
};

function statusTone(status: RunStatusEnum): { tone: "muted" | "cyan" | "emerald" | "rose"; pulse: boolean; label: string } {
  switch (status) {
    case "queued":    return { tone: "muted",   pulse: false, label: "queued" };
    case "running":   return { tone: "cyan",    pulse: true,  label: "running" };
    case "completed": return { tone: "emerald", pulse: false, label: "completed" };
    case "failed":    return { tone: "rose",    pulse: false, label: "failed" };
    case "cancelled": return { tone: "rose",    pulse: false, label: "CANCELLED" };
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

const COLS: { key: string; label: string; ariaLabel?: string }[] = [
  { key: "selected", label: "", ariaLabel: "Selected run" },
  { key: "favorite", label: "", ariaLabel: "Favorite" },
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

const visuallyHiddenStyle: CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0, 0, 0, 0)",
  whiteSpace: "nowrap",
  border: 0,
};

export function RunTable({ rows, selectedId, onSelect, onToggleFavorite, favoriteBusyId, favoritesDisabled }: Props) {
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
                aria-label={c.ariaLabel}
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
                {c.label || <span style={visuallyHiddenStyle}>{c.ariaLabel}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const status = statusTone(r.status);
            const isSelected = r.run_id === selectedId;
            const favoriteBusy = favoriteBusyId === r.run_id;
            const favoriteDisabled = Boolean(favoritesDisabled || favoriteBusy);
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
                  // Ignore key events bubbling from nested controls (favorite ★ button)
                  if (e.target !== e.currentTarget) return;
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
                      background: isSelected ? "var(--violet)" : "transparent",
                      borderRadius: 2,
                    }}
                  />
                </td>
                <td style={{ padding: "8px 12px", width: 28 }}>
                  <button
                    type="button"
                    aria-label={r.favorited ? `Unfavorite ${r.run_id}` : `Favorite ${r.run_id}`}
                    aria-pressed={r.favorited ?? false}
                    aria-busy={favoriteDisabled ? "true" : undefined}
                    disabled={favoriteDisabled}
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleFavorite?.(r.run_id);
                    }}
                    style={{
                      background: "transparent",
                      border: "none",
                      cursor: favoriteDisabled ? "not-allowed" : "pointer",
                      fontSize: 14,
                      color: r.favorited ? "var(--gold)" : "var(--muted)",
                      opacity: favoriteDisabled ? 0.5 : 1,
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
                  <Pill tone={status.tone} size="xs" pulse={status.pulse} live>{status.label}</Pill>
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
