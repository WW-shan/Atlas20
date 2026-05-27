import type { ReactNode } from "react";

export type SectionHeaderProps = {
  children: string;
  rightSlot?: ReactNode;
};

export function SectionHeader({ children, rightSlot }: SectionHeaderProps) {
  return (
    <div
      role="heading"
      aria-level={3}
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 8,
        marginBottom: 12,
      }}
    >
      <span className="section-label">{children}</span>
      {rightSlot}
    </div>
  );
}
