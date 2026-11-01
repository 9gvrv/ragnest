"use client";

import { useId, type ReactNode } from "react";
import { ChevronDownIcon } from "@/components/workspace/icons";

type SidebarSectionProps = {
  title: string;
  count: number;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
  className?: string;
};

/**
 * A sidebar section whose body collapses with a height transition. The content
 * stays mounted so its state survives toggling; `inert` keeps it out of the tab
 * order while it is closed.
 */
export function SidebarSection({
  title,
  count,
  open,
  onToggle,
  children,
  className,
}: SidebarSectionProps) {
  const id = useId();
  const headingId = `${id}-heading`;
  const contentId = `${id}-content`;

  return (
    <section
      aria-labelledby={headingId}
      className={["border-b border-border", className].filter(Boolean).join(" ")}
    >
      <h2 id={headingId}>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={onToggle}
          className="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors duration-150 hover:bg-surface"
        >
          <ChevronDownIcon
            className={[
              "size-3.5 shrink-0 text-muted transition-transform duration-150",
              open ? "" : "-rotate-90",
            ].join(" ")}
          />
          <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">
            {title}
          </span>
          <span className="rounded-full border border-border bg-elevated px-1.5 py-0.5 font-mono text-[11px] leading-none tabular-nums text-muted">
            {count}
          </span>
        </button>
      </h2>

      <div
        id={contentId}
        className={[
          "grid transition-[grid-template-rows] duration-200 ease-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        ].join(" ")}
      >
        <div className="overflow-hidden" inert={!open}>
          {children}
        </div>
      </div>
    </section>
  );
}
