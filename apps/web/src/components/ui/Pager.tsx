export type PagerProps = {
  total: number;
  page: number;
  pageSize: number;
  disabled?: boolean;
  onChange: (page: number) => void;
};

const MAX_UNWINDOWED_PAGES = 7;

// First, last and the current page's neighbours, with gaps in between, so a
// long run history does not render hundreds of buttons in one row.
function visiblePages(page: number, totalPages: number): (number | "gap")[] {
  if (totalPages <= MAX_UNWINDOWED_PAGES) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const anchors = [...new Set([1, page - 1, page, page + 1, totalPages])]
    .filter((p) => p >= 1 && p <= totalPages)
    .sort((a, b) => a - b);
  return anchors.flatMap((p, i) => (i > 0 && p - anchors[i - 1] > 1 ? ["gap" as const, p] : [p]));
}

export function Pager({ total, page, pageSize, disabled, onChange }: PagerProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pages = visiblePages(page, totalPages);
  const from = Math.min((page - 1) * pageSize + 1, total);
  const to = Math.min(page * pageSize, total);

  return (
    <div
      style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0" }}
      role="navigation"
      aria-label="Pagination"
    >
      <span className="muted" style={{ fontSize: 12 }}>
        Showing <span className="mono">{from}</span>–<span className="mono">{to}</span> of{" "}
        <span className="mono">{total.toLocaleString()}</span>
      </span>
      <div style={{ display: "flex", gap: 4 }}>
        {pages.map((p, index) => {
          if (p === "gap") {
            return (
              <span key={`gap-${index}`} aria-hidden="true" className="mono muted" style={{ minWidth: 20, textAlign: "center", fontSize: 12, alignSelf: "center" }}>
                …
              </span>
            );
          }
          const buttonDisabled = Boolean(disabled || p === page);
          return (
            <button
              key={p}
              type="button"
              onClick={() => onChange(p)}
              disabled={buttonDisabled}
              aria-label={`Page ${p}`}
              aria-current={p === page ? "page" : undefined}
              className="mono"
              style={{
                minWidth: 28,
                height: 28,
                border: "none",
                borderRadius: 4,
                fontSize: 12,
                fontFamily: "var(--font-mono)",
                fontWeight: p === page ? 700 : 400,
                color: p === page ? "var(--bg)" : "var(--muted)",
                background: p === page ? "var(--violet)" : "transparent",
                cursor: buttonDisabled ? "default" : "pointer",
                opacity: disabled && p !== page ? 0.5 : 1,
              }}
            >
              {p}
            </button>
          );
        })}
      </div>
    </div>
  );
}
