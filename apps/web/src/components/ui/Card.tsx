import type { ReactNode } from "react";

type CardProps = {
  variant?: "default" | "hero" | "report";
  header?: ReactNode;
  children: ReactNode;
  style?: React.CSSProperties;
};

export function Card({ variant = "default", header, children, style }: CardProps) {
  return (
    <div
      className={variant === "hero" ? "card card--hero" : "card"}
      style={{
        padding: 20,
        ...(variant === "hero" ? { minHeight: 180 } : {}),
        ...style,
      }}
    >
      {header && (
        <div style={{ marginBottom: 12 }}>{header}</div>
      )}
      {children}
    </div>
  );
}
