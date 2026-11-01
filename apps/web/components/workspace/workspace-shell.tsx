"use client";

import { useEffect, useRef, useState } from "react";
import { ChatArea } from "@/components/workspace/chat-area";
import { WorkspaceSidebar } from "@/components/workspace/workspace-sidebar";
import { WorkspaceTopbar } from "@/components/workspace/workspace-topbar";
import type {
  ApiDocument,
  ApiMember,
  ApiRole,
  ApiUser,
  ApiWorkspace,
} from "@/lib/api";
import type { ChatMessage, WorkspaceChat } from "@/lib/chats";

type WorkspaceShellProps = {
  workspace: ApiWorkspace;
  me: ApiUser;
  myRole: ApiRole;
  allDocuments: ApiDocument[];
  documents: ApiDocument[];
  mine: boolean;
  members: ApiMember[];
  chats: WorkspaceChat[];
  messages: ChatMessage[];
};

export function WorkspaceShell({
  workspace,
  me,
  myRole,
  allDocuments,
  documents,
  mine,
  members,
  chats,
  messages,
}: WorkspaceShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(true);
  const [membersOpen, setMembersOpen] = useState(true);
  const uploadButtonRef = useRef<HTMLButtonElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  function handleNewChat() {
    setMobileOpen(false);
    requestAnimationFrame(() => composerRef.current?.focus());
  }

  useEffect(() => {
    if (!mobileOpen) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      setMobileOpen(false);
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen]);

  return (
    <div className="flex h-full min-h-0">
      {mobileOpen ? (
        <button
          type="button"
          tabIndex={-1}
          aria-hidden="true"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-30 bg-background/70 lg:hidden"
        />
      ) : null}

      <WorkspaceSidebar
        workspace={workspace}
        me={me}
        myRole={myRole}
        allDocumentsCount={allDocuments.length}
        documents={documents}
        mine={mine}
        documentsOpen={documentsOpen}
        onToggleDocuments={() => setDocumentsOpen((value) => !value)}
        members={members}
        membersOpen={membersOpen}
        onToggleMembers={() => setMembersOpen((value) => !value)}
        chats={chats}
        onNewChat={handleNewChat}
        uploadButtonRef={uploadButtonRef}
        open={mobileOpen}
        collapsed={collapsed}
        onClose={() => setMobileOpen(false)}
        onCollapse={() => setCollapsed(true)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <WorkspaceTopbar
          workspace={workspace}
          collapsed={collapsed}
          onOpenMobile={() => setMobileOpen(true)}
          onExpand={() => setCollapsed(false)}
        />
        <ChatArea
          workspaceName={workspace.name}
          messages={messages}
          composerRef={composerRef}
        />
      </div>
    </div>
  );
}
