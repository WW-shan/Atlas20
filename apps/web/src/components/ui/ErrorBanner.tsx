export type ErrorBannerProps = {
  message: string;
  onRetry?: () => void;
};

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 16px",
        borderTop: "3px solid var(--rose)",
        background: "rgba(244,63,94,0.06)",
        borderRadius: "var(--radius-card)",
        fontSize: 13,
      }}
    >
      <span style={{ color: "var(--rose)", fontSize: 16 }}>⚠</span>
      <span style={{ flex: 1 }}>{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          style={{
            padding: "4px 12px",
            fontSize: 12,
            color: "var(--rose)",
            background: "transparent",
            border: "1px solid var(--rose)",
            borderRadius: "var(--radius-input)",
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
