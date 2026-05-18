export type PagerProps = {
  total: number;
  page: number;
  pageSize: number;
  onChange: (page: number) => void;
};

export function Pager({ total, page, pageSize, onChange }: PagerProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);
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
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            disabled={p === page}
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
              background: p === page ? "var(--gold)" : "transparent",
              cursor: p === page ? "default" : "pointer",
            }}
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
