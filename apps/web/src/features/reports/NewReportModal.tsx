import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { Dialog } from "../../components/ui/Dialog";
import type { GenerateReportRequest, ReportFormat } from "../../lib/api";

const REPORT_TYPES: GenerateReportRequest["type"][] = ["weekly", "run", "compare", "universe"];
const FORMATS: ReportFormat[] = ["markdown", "pdf", "png", "csv"];

type Props = {
  open: boolean;
  presets: string[];
  onClose: () => void;
  onGenerate: (payload: GenerateReportRequest) => Promise<void>;
};

export function NewReportModal({ open, presets, onClose, onGenerate }: Props) {
  const [type, setType] = useState<GenerateReportRequest["type"]>("weekly");
  const [formats, setFormats] = useState<ReportFormat[]>(["markdown"]);
  const [strategy, setStrategy] = useState("");
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setType("weekly");
    setFormats(["markdown"]);
    setStrategy(presets[0] ?? "");
    setNotes("");
    setPending(false);
    setError(null);
  }, [open, presets]);

  const needsStrategy = type === "run" || type === "compare";
  const uniquePresets = useMemo(() => {
    return Array.from(new Set(presets.filter((preset) => preset.trim().length > 0)));
  }, [presets]);

  useEffect(() => {
    if (!open || uniquePresets.length === 0) return;
    if (!uniquePresets.includes(strategy)) setStrategy(uniquePresets[0]);
  }, [open, strategy, uniquePresets]);

  const toggleFormat = (format: ReportFormat) => {
    setError(null);
    setFormats((current) =>
      current.includes(format)
        ? current.filter((item) => item !== format)
        : [...current, format],
    );
  };

  const handleGenerate = () => {
    if (pending || formats.length === 0) return;
    setError(null);
    const payload: GenerateReportRequest = {
      type,
      formats,
      strategy: needsStrategy && strategy ? strategy : undefined,
      notes: notes.trim() ? notes.trim() : undefined,
    };
    setPending(true);
    void onGenerate(payload)
      .then(() => onClose())
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Generation failed");
      })
      .finally(() => setPending(false));
  };

  return (
    <Dialog open={open} onClose={onClose} ariaLabelledBy="new-report-modal-title" width={620}>
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
          <h2 id="new-report-modal-title" style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>New report</h2>
          <button
            type="button"
            aria-label="Close new report"
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-input)",
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            <X size={15} aria-hidden="true" />
          </button>
        </div>

        <div role="radiogroup" aria-label="Report type" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 8 }}>
          {REPORT_TYPES.map((item) => (
            <label
              key={item}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 10px",
                borderRadius: "var(--radius-input)",
                border: `1px solid ${type === item ? "var(--violet)" : "var(--border)"}`,
                color: type === item ? "var(--violet)" : "var(--text)",
                background: type === item ? "rgba(139,92,246,0.10)" : "transparent",
                fontSize: 12,
                textTransform: "uppercase",
                cursor: "pointer",
              }}
            >
              <input
                type="radio"
                name="report-type"
                checked={type === item}
                onChange={() => {
                  setError(null);
                  setType(item);
                }}
              />
              {item}
            </label>
          ))}
        </div>

        <div role="group" aria-label="Report formats" style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 8 }}>
          {FORMATS.map((format) => (
            <label
              key={format}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 10px",
                borderRadius: "var(--radius-input)",
                border: `1px solid ${formats.includes(format) ? "var(--violet)" : "var(--border)"}`,
                color: formats.includes(format) ? "var(--violet)" : "var(--text)",
                background: formats.includes(format) ? "rgba(139,92,246,0.10)" : "transparent",
                fontSize: 12,
                textTransform: "uppercase",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={formats.includes(format)}
                onChange={() => toggleFormat(format)}
              />
              {format}
            </label>
          ))}
        </div>

        {needsStrategy && (
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, color: "var(--muted)" }}>
            Strategy
            <select
              value={strategy}
              onChange={(event) => {
                setError(null);
                setStrategy(event.target.value);
              }}
              disabled={uniquePresets.length === 0}
              style={{
                minHeight: 36,
                borderRadius: "var(--radius-input)",
                border: "1px solid var(--border)",
                background: "var(--bg)",
                color: "var(--text)",
                padding: "0 10px",
                font: "inherit",
              }}
            >
              {uniquePresets.length === 0 ? (
                <option value="">No strategies available</option>
              ) : uniquePresets.map((preset) => (
                <option key={preset} value={preset}>{preset}</option>
              ))}
            </select>
          </label>
        )}

        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, color: "var(--muted)" }}>
          Notes
          <textarea
            aria-label="Notes"
            value={notes}
            onChange={(event) => {
              setError(null);
              setNotes(event.target.value);
            }}
            rows={4}
            style={{
              resize: "vertical",
              minHeight: 92,
              borderRadius: "var(--radius-input)",
              border: "1px solid var(--border)",
              background: "var(--bg)",
              color: "var(--text)",
              padding: 10,
              font: "inherit",
              fontSize: 13,
            }}
          />
        </label>

        {error && (
          <div
            role="alert"
            style={{
              padding: "10px 12px",
              borderTop: "3px solid var(--rose)",
              borderRadius: "var(--radius-card)",
              background: "rgba(244,63,94,0.06)",
              color: "var(--text)",
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button variant="outline-muted" disabled={pending} onClick={onClose}>Cancel</Button>
          <Button variant="gold" loading={pending} disabled={formats.length === 0} onClick={handleGenerate}>Generate</Button>
        </div>
      </div>
    </Dialog>
  );
}
