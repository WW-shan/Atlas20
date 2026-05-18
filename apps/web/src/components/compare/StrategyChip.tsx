import type { CompareSelectionItem } from "../../lib/api";

type Props = {
  item: CompareSelectionItem;
  onRemove?: (id: string) => void;
};

const toneStyles: Record<CompareSelectionItem["tone"], { color: string; border: string; bg: string }> = {
  gold:    { color: "var(--gold)",    border: "var(--gold)",    bg: "rgba(245,158,11,0.08)" },
  violet:  { color: "var(--violet)",  border: "var(--violet)",  bg: "rgba(139,92,246,0.08)" },
  cyan:    { color: "var(--cyan)",    border: "var(--cyan)",    bg: "rgba(6,182,212,0.08)" },
  emerald: { color: "var(--emerald)", border: "var(--emerald)", bg: "rgba(16,185,129,0.08)" },
};

export function StrategyChip({ item, onRemove }: Props) {
  const t = toneStyles[item.tone];
  return (
    <span
      role="listitem"
      aria-label={`Strategy ${item.label}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 12px",
        borderRadius: "var(--radius-pill)",
        border: `1px solid ${t.border}`,
        background: t.bg,
        color: t.color,
        fontFamily: "var(--font-sans)",
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: "0.04em",
      }}
    >
      <span
        aria-hidden
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: t.color,
          display: "inline-block",
        }}
      />
      <span>{item.label}</span>
      {onRemove && (
        <button
          type="button"
          aria-label={`Remove ${item.label}`}
          onClick={() => onRemove(item.id)}
          style={{
            background: "transparent",
            border: "none",
            color: t.color,
            cursor: "pointer",
            padding: 0,
            marginLeft: 4,
            fontSize: 14,
            lineHeight: 1,
          }}
        >
          ×
        </button>
      )}
    </span>
  );
}

export function AddStrategyChip({ onClick }: { onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Add strategy"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "6px 12px",
        borderRadius: "var(--radius-pill)",
        border: "1px dashed var(--border)",
        background: "transparent",
        color: "var(--muted)",
        fontFamily: "var(--font-sans)",
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: "0.04em",
        cursor: "pointer",
      }}
    >
      + ADD STRATEGY
    </button>
  );
}
