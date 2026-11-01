"use client";

import {
  MenuIcon,
  PanelLeftIcon,
} from "@/components/workspace/icons";
import type { ApiWorkspace } from "@/lib/api";

type WorkspaceTopbarProps = {
  workspace: ApiWorkspace;
  collapsed: boolean;
  onOpenMobile: () => void;
  onExpand: () => void;
};

export function WorkspaceTopbar({
  workspace,
  collapsed,
  onOpenMobile,
  onExpand,
}: WorkspaceTopbarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur-sm sm:px-5">
      <button
        type="button"
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

      <h1 className="min-w-0 truncate text-sm font-medium text-foreground">
        {workspace.name}
      </h1>
    </header>
  );
}
