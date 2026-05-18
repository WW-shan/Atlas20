import type { ReactNode } from "react";

export function AppShell(props: {
  actions: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <header className="topnav" style={{ height: "var(--topnav-h)" }}>
        <div className="topnav-left">
          <span className="topnav-wordmark">ATLAS20</span>
          <span className="topnav-tag muted">Research Console</span>
        </div>
        <div className="topnav-center">{props.actions}</div>
        <div className="topnav-right">
          <div
            className="topnav-search"
            role="search"
            aria-label="Search"
          >
            <input
              type="search"
              placeholder="Search strategies, metrics, runs…"
              className="topnav-search__input"
              aria-label="Search strategies, metrics, runs"
            />
          </div>
        </div>
      </header>
      <main>{props.children}</main>
    </div>
  );
}
