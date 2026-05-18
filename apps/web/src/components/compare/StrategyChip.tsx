import type { CompareSelectionItem } from "../../lib/api";

type Props = {
  item: CompareSelectionItem;
  onRemove?: (id: string) => void;
};

const dotColors: Record<CompareSelectionItem["tone"], string> = {
  gold:    "var(--gold)",
  violet:  "var(--violet)",
  cyan:    "var(--cyan)",
  emerald: "var(--emerald)",
};

export function StrategyChip({ item, onRemove }: Props) {
  // Gold is on the SPEC §1.1 restraint whitelist for chart lines + best-cell
  // tint + diagonal heatmap only. Strategy chips keep a tone-matching dot so
  // users can map chip→line in the legend, but the chip surface itself uses
  // neutral border/text/bg to honour gold restraint.
  return (
    <span
      role="listitem"
      aria-label={`Strategy ${item.label}`}
      data-tone={item.tone}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 12px",
        borderRadius: "var(--radius-pill)",
        border: "1px solid var(--border)",
        background: "var(--surface)",
        color: "var(--text)",
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
          background: dotColors[item.tone],
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
            color: "var(--muted)",
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
