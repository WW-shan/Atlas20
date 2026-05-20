import { useEffect, useMemo, useState } from "react";
import { Check, Search, X } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { Dialog } from "../../components/ui/Dialog";

type Props = {
  open: boolean;
  strategies: string[];
  selected: string[];
  onClose: () => void;
  onAdd: (selected: string[]) => void;
};

export function AddStrategyModal({ open, strategies, selected, onClose, onAdd }: Props) {
  const [query, setQuery] = useState("");
  const [selectedItems, setSelectedItems] = useState<string[]>(selected);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setSelectedItems(selected);
  }, [open, selected]);

  const uniqueStrategies = useMemo(() => {
    return Array.from(new Set(strategies.filter((strategy) => strategy.trim().length > 0)));
  }, [strategies]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return uniqueStrategies;
    return uniqueStrategies.filter((strategy) => strategy.toLowerCase().includes(needle));
  }, [query, uniqueStrategies]);

  const selectedSet = useMemo(() => new Set(selectedItems), [selectedItems]);

  const toggle = (strategy: string) => {
    setSelectedItems((current) =>
      current.includes(strategy)
        ? current.filter((item) => item !== strategy)
        : [...current, strategy],
    );
  };

  return (
    <Dialog open={open} onClose={onClose} ariaLabel="Add strategy">
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Add strategy</h2>
            <span className="mono muted" style={{ display: "block", marginTop: 4, fontSize: 11 }}>
              {selectedItems.length} selected
            </span>
          </div>
          <button
            type="button"
            aria-label="Close add strategy"
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

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 10px",
            borderRadius: "var(--radius-input)",
            border: "1px solid var(--border)",
            background: "var(--bg)",
          }}
        >
          <Search size={14} aria-hidden="true" style={{ color: "var(--muted)" }} />
          <input
            type="search"
            aria-label="Search strategies"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search strategies"
            style={{
              flex: 1,
              minWidth: 0,
              border: "none",
              outline: "none",
              background: "transparent",
              color: "var(--text)",
              font: "inherit",
              fontSize: 13,
            }}
          />
        </label>

        <div
          role="listbox"
          aria-label="Available strategies"
          aria-multiselectable="true"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 6,
            maxHeight: 280,
            overflowY: "auto",
          }}
        >
          {filtered.map((strategy) => {
            const active = selectedSet.has(strategy);
            return (
              <button
                key={strategy}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => toggle(strategy)}
                style={{
                  display: "grid",
                  gridTemplateColumns: "20px minmax(0, 1fr)",
                  alignItems: "center",
                  gap: 10,
                  width: "100%",
                  padding: "9px 10px",
                  borderRadius: "var(--radius-input)",
                  border: `1px solid ${active ? "var(--violet)" : "var(--border)"}`,
                  background: active ? "rgba(139,92,246,0.10)" : "transparent",
                  color: "var(--text)",
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: "var(--font-sans)",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: 18,
                    height: 18,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 4,
                    border: `1px solid ${active ? "var(--violet)" : "var(--border)"}`,
                    color: active ? "var(--violet)" : "transparent",
                  }}
                >
                  <Check size={13} />
                </span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13 }}>
                  {strategy}
                </span>
              </button>
            );
          })}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button variant="outline-muted" onClick={onClose}>Cancel</Button>
          <Button variant="gold" disabled={selectedItems.length === 0} onClick={() => onAdd(selectedItems)}>Add</Button>
        </div>
      </div>
    </Dialog>
  );
}
