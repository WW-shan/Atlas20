export type EmptyStateProps = {
  title: string;
  sub?: string;
  action?: { label: string; onClick: () => void };
};

export function EmptyState({ title, sub, action }: EmptyStateProps) {
  return (
    <div
      role="status"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 48,
        gap: 8,
        textAlign: "center",
      }}
    >
      <span style={{ fontSize: 14, color: "var(--text)" }}>{title}</span>
      {sub && <span className="muted" style={{ fontSize: 13 }}>{sub}</span>}
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          style={{
            marginTop: 12,
            padding: "6px 16px",
            fontSize: 13,
            color: "var(--violet)",
            background: "transparent",
            border: "1px solid var(--violet)",
            borderRadius: "var(--radius-input)",
            cursor: "pointer",
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
