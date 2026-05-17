import type { ReactNode } from "react";

export function Panel(props: {
  title?: string;
  eyebrow?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`panel ${props.className ?? ""}`}>
      {props.eyebrow ? <div className="panel__eyebrow">{props.eyebrow}</div> : null}
      {props.title ? <h2 className="panel__title">{props.title}</h2> : null}
      {props.children}
    </section>
  );
}
