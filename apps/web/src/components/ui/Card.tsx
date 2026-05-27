import type { ReactNode } from "react";

export type CardProps = {
  variant?: "default" | "hero" | "report";
  header?: ReactNode;
  thumbnail?: ReactNode;
  children: ReactNode;
  style?: React.CSSProperties;
  ariaLabel?: string;
};

const variantClass: Record<NonNullable<CardProps["variant"]>, string> = {
  default: "card",
  hero:    "card card--hero",
  report:  "card card--report",
};

export function Card({ variant = "default", header, thumbnail, children, style, ariaLabel }: CardProps) {
  return (
    <section
      aria-label={ariaLabel}
      className={variantClass[variant]}
      data-variant={variant}
      style={{
        minWidth: 0,
        padding: variant === "hero" ? "12px 20px" : variant === "report" ? 0 : 20,
        ...style,
      }}
    >
      {variant === "report" && thumbnail && (
        <div className="card__thumbnail" style={{ height: 96, overflow: "hidden" }}>
          {thumbnail}
        </div>
      )}
      {variant === "report" ? (
        <div style={{ padding: 16 }}>
          {header && <div style={{ marginBottom: 12 }}>{header}</div>}
          {children}
        </div>
      ) : (
        <>
          {header && <div style={{ marginBottom: 12 }}>{header}</div>}
          {children}
        </>
      )}
    </section>
  );
}
