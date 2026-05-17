import type { ReactNode } from "react";

export function AppShell(props: {
  title: string;
  subtitle: string;
  actions: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">ATLAS20 ROTATION</div>
          <h1>{props.title}</h1>
          <p>{props.subtitle}</p>
        </div>
        <div className="topbar__actions">{props.actions}</div>
      </header>
      <main>{props.children}</main>
    </div>
  );
}
