import type { ReactNode } from "react";

type SectionHeaderProps = {
  children: string;
  rightSlot?: ReactNode;
};

export function SectionHeader({ children, rightSlot }: SectionHeaderProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 12,
      }}
    >
      <span className="section-label">{children}</span>
      {rightSlot}
    </div>
  );
}
