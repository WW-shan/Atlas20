import type { RunRowSummary } from "../../lib/api";
import { Pill } from "../ui/Pill";
import { SectionHeader } from "../ui/SectionHeader";

type Props = {
  runs: RunRowSummary[];
  onViewAll?: () => void;
};

function statusToToneAndLabel(status: RunRowSummary["status"]): { tone: "cyan" | "emerald" | "rose" | "muted"; pulse: boolean; label: string } {
  switch (status) {
    case "running":   return { tone: "cyan",    pulse: true,  label: "RUNNING" };
    case "completed": return { tone: "emerald", pulse: false, label: "COMPLETED" };
    case "failed":    return { tone: "rose",    pulse: false, label: "FAILED" };
    case "queued":    return { tone: "muted",   pulse: false, label: "QUEUED" };
  }
}

function statusToProgress(status: RunRowSummary["status"]): { fill: string; widthPct: number } | null {
  switch (status) {
    case "running":   return { fill: "var(--cyan)",    widthPct: 50 };
    case "completed": return { fill: "var(--emerald)", widthPct: 100 };
    case "failed":    return { fill: "var(--rose)",    widthPct: 100 };
    case "queued":    return null;
  }
}

function fmtTime(s?: number): string {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export function RunQueue({ runs, onViewAll }: Props) {
  const activeCount = runs.filter((r) => r.status === "running").length;

  return (
    <aside
      style={{
        width: 320,
        flex: "0 0 320px",
        padding: 20,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-card)",
      }}
      aria-label="Run queue"
    >
      <SectionHeader rightSlot={<Pill tone="cyan" size="xs">{activeCount} ACTIVE</Pill>}>
        RUN QUEUE
      </SectionHeader>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {runs.slice(0, 6).map((run) => {
          const s = statusToToneAndLabel(run.status);
          const progress = statusToProgress(run.status);

          return (
            <div
              key={run.run_id}
              style={{
                padding: 12,
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--bg)",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <Pill tone={s.tone} pulse={s.pulse} size="xs">{s.label}</Pill>
                <span className="mono muted" style={{ fontSize: 11 }}>{run.run_id}</span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 12, fontWeight: 500 }}>{run.strategy}</span>
                <span className="muted mono" style={{ fontSize: 10 }}>{run.params_summary}</span>
              </div>

              {progress && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ flex: 1, height: 3, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ width: `${progress.widthPct}%`, height: "100%", background: progress.fill }} />
                  </div>
                  <span className="mono muted" style={{ fontSize: 10 }}>
                    {fmtTime(run.duration_s)}{run.eta_s ? ` / ~${fmtTime(run.eta_s)}` : ""}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="muted" style={{ fontSize: 11 }}>Showing {Math.min(runs.length, 6)} of {runs.length}</span>
        {onViewAll && (
          <button
            type="button"
            onClick={onViewAll}
            style={{ fontSize: 12, color: "var(--muted)", padding: 0, background: "transparent" }}
          >
            View all →
          </button>
        )}
      </div>
    </aside>
  );
}
