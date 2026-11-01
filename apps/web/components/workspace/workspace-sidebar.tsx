"use client";

import Link from "next/link";
import type { RefObject } from "react";
import { DeleteWorkspaceButton } from "@/components/delete-workspace-button";
import { LogoMark } from "@/components/logo";
import { DocumentsSection } from "@/components/workspace/documents-section";
import {
  ArrowLeftIcon,
  MoreHorizontalIcon,
  PanelLeftIcon,
  XIcon,
} from "@/components/workspace/icons";
import { MembersSection } from "@/components/workspace/members-section";
import { Menu } from "@/components/workspace/menu";
import { UserMenu } from "@/components/workspace/user-menu";
import type {
  ApiDocument,
  ApiMember,
  ApiRole,
  ApiUser,
  ApiWorkspace,
} from "@/lib/api";

type WorkspaceSidebarProps = {
  workspace: ApiWorkspace;
  me: ApiUser;
  myRole: ApiRole;
  allDocumentsCount: number;
  documents: ApiDocument[];
  mine: boolean;
  documentsOpen: boolean;
  onToggleDocuments: () => void;
  members: ApiMember[];
  membersOpen: boolean;
  onToggleMembers: () => void;
  uploadButtonRef: RefObject<HTMLButtonElement | null>;
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
  onCollapse: () => void;
};

export function WorkspaceSidebar({
  workspace,
  me,
  myRole,
  allDocumentsCount,
  documents,
  mine,
  documentsOpen,
  onToggleDocuments,
  members,
  membersOpen,
  onToggleMembers,
  uploadButtonRef,
  open,
  collapsed,
  onClose,
  onCollapse,
}: WorkspaceSidebarProps) {
  return (
    <aside
      aria-label="Workspace sidebar"
      className={[
        "fixed inset-y-0 left-0 z-40 flex w-72 max-w-[85vw] flex-col overflow-hidden border-r border-border bg-background transition-transform duration-200 ease-out lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:transition-none",
        open ? "translate-x-0" : "-translate-x-full",
        collapsed ? "lg:hidden" : "",
      ].join(" ")}
    >
      <div className="flex h-14 shrink-0 items-center gap-1 border-b border-border px-2.5">
        <Link
          href="/workspaces"
          className="flex min-w-0 items-center gap-2 rounded-md px-1.5 py-1.5 transition-colors duration-150 hover:bg-surface"
        >
          <LogoMark />
          <span className="truncate text-sm font-semibold tracking-tight text-foreground">
            Ragnest
          </span>
        </Link>

        <div className="ml-auto flex shrink-0 items-center gap-0.5">
          {myRole === "creator" ? (
            <Menu
              label="Workspace options"
              align="end"
              triggerClassName="grid size-8 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground"
              trigger={<MoreHorizontalIcon className="size-4" />}
            >
              <DeleteWorkspaceButton
                workspaceId={workspace.id}
                workspaceName={workspace.name}
                variant="menu"
              />
            </Menu>
          ) : null}

          <button
            type="button"
            onClick={onCollapse}
            aria-label="Collapse sidebar"
            className="hidden size-8 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground lg:grid"
          >
            <PanelLeftIcon className="size-4" />
          </button>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="grid size-8 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground lg:hidden"
          >
            <XIcon className="size-4" />
          </button>
        </div>
      </div>

      <div className="shrink-0 px-4 pt-4 pb-3">
        <p className="truncate text-base font-semibold tracking-[-0.01em] text-foreground">
          {workspace.name}
        </p>
        <Link
          href="/workspaces"
          className="mt-1 inline-flex items-center gap-1 rounded-sm text-xs text-muted transition-colors duration-150 hover:text-foreground"
        >
          <ArrowLeftIcon className="size-3.5" />
          All workspaces
        </Link>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="max-h-[60%] shrink-0 overflow-y-auto">
          <DocumentsSection
            workspaceId={workspace.id}
            documentsPath={`/workspaces/${workspace.id}`}
            totalCount={allDocumentsCount}
            documents={documents}
            mine={mine}
            myRole={myRole}
            userId={me.id}
            open={documentsOpen}
            onToggle={onToggleDocuments}
            uploadButtonRef={uploadButtonRef}
          />
          <MembersSection
            workspaceId={workspace.id}
            members={members}
            me={me}
            myRole={myRole}
            open={membersOpen}
            onToggle={onToggleMembers}
          />
        </div>
        <div className="min-h-0 flex-1" />
      </div>

      <footer className="shrink-0 border-t border-border p-2">
        <UserMenu me={me} />
      </footer>
    </aside>
  );
}
