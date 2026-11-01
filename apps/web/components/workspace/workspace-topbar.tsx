"use client";

import type { RefObject } from "react";
import { MenuIcon, PanelLeftIcon } from "@/components/workspace/icons";

type WorkspaceTopbarProps = {
  chatTitle: string;
  documentCount: number;
  collapsed: boolean;
  triggerRef: RefObject<HTMLButtonElement | null>;
  onOpenMobile: () => void;
  onExpand: () => void;
};

export function WorkspaceTopbar({
  chatTitle,
  documentCount,
  collapsed,
  triggerRef,
  onOpenMobile,
  onExpand,
}: WorkspaceTopbarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur-sm sm:px-5">
      <button
        type="button"
        ref={triggerRef}
        onClick={onOpenMobile}
        aria-label="Open sidebar"
        className="grid size-9 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground lg:hidden"
      >
        <MenuIcon className="size-4" />
      </button>

      {collapsed ? (
        <button
          type="button"
          onClick={onExpand}
          aria-label="Expand sidebar"
          className="hidden size-9 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground lg:grid"
        >
          <PanelLeftIcon className="size-4" />
        </button>
      ) : null}

      <h1 className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
        {chatTitle}
      </h1>

      <p className="hidden shrink-0 text-xs text-muted sm:block">
        {documentCount === 0
          ? "No documents yet"
          : `Searching ${documentCount} document${
              documentCount === 1 ? "" : "s"
            }`}
      </p>
    </header>
  );
}
