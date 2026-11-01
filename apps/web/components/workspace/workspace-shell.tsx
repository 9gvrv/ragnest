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
  const [uploadRequest, setUploadRequest] = useState(0);
  const uploadButtonRef = useRef<HTMLButtonElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const sidebarCloseRef = useRef<HTMLButtonElement>(null);
  const mobileTriggerRef = useRef<HTMLButtonElement>(null);

  function closeMobile() {
    setMobileOpen(false);
    mobileTriggerRef.current?.focus();
  }

  function handleNewChat() {
    setMobileOpen(false);
    requestAnimationFrame(() => composerRef.current?.focus());
  }

  function requestUpload() {
    setDocumentsOpen(true);
    setCollapsed(false);
    if (window.matchMedia("(max-width: 1023px)").matches) setMobileOpen(true);
    setUploadRequest((value) => value + 1);
  }

  useEffect(() => {
    if (uploadRequest === 0) return;
    uploadButtonRef.current?.focus();
  }, [uploadRequest]);

  useEffect(() => {
    if (!mobileOpen) return;
    sidebarCloseRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      if (document.querySelector("dialog[open]")) return;
      setMobileOpen(false);
      mobileTriggerRef.current?.focus();
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
          onClick={closeMobile}
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
        closeButtonRef={sidebarCloseRef}
        open={mobileOpen}
        collapsed={collapsed}
        onClose={closeMobile}
        onCollapse={() => setCollapsed(true)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <WorkspaceTopbar
          workspace={workspace}
          collapsed={collapsed}
          triggerRef={mobileTriggerRef}
          onOpenMobile={() => setMobileOpen(true)}
          onExpand={() => setCollapsed(false)}
        />
        <ChatArea
          workspaceName={workspace.name}
          hasDocuments={allDocuments.length > 0}
          messages={messages}
          composerRef={composerRef}
          onUploadRequest={requestUpload}
        />
      </div>
    </div>
  );
}
