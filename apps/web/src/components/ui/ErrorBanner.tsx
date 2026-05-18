export type ErrorBannerProps = {
  message: string;
  onRetry?: () => void;
};

function AlertTriangleIcon() {
  return (
    <svg
      aria-hidden="true"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}

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
      <span style={{ color: "var(--rose)", display: "inline-flex" }}>
        <AlertTriangleIcon />
      </span>
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
