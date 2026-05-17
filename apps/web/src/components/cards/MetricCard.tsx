import type { ReactNode } from "react";

export function MetricCard(props: {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "risk" | "accent";
  icon?: ReactNode;
}) {
  return (
    <div className={`metric-card metric-card--${props.tone ?? "neutral"}`}>
      <div className="metric-card__label">
        {props.icon}
        <span>{props.label}</span>
      </div>
      <strong>{props.value}</strong>
    </div>
  );
}
