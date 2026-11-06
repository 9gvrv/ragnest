"use client";

import Link from "next/link";
import type { RefObject } from "react";
import { DeleteDocumentButton } from "@/components/delete-document-button";
import { SidebarSection } from "@/components/workspace/sidebar-section";
import { sidebarScroll } from "@/components/workspace/sidebar-scroll";
import { UploadDocumentForm } from "@/components/upload-document-form";
import type { ApiDocument, ApiRole } from "@/lib/api";
import { canManageDocument, formatBytes } from "@/lib/documents";
import { documentKind } from "@/lib/workspace";

type DocumentsSectionProps = {
  workspaceId: string;
  documentsPath: string;
  totalCount: number;
  documents: ApiDocument[];
  mine: boolean;
  myRole: ApiRole;
  userId: string;
  open: boolean;
  onToggle: () => void;
  uploadButtonRef: RefObject<HTMLButtonElement | null>;
};

export function DocumentsSection({
  workspaceId,
  documentsPath,
  totalCount,
  documents,
  mine,
  myRole,
  userId,
  open,
  onToggle,
  uploadButtonRef,
}: DocumentsSectionProps) {
  return (
    <SidebarSection
      title="Documents"
      count={totalCount}
      open={open}
      onToggle={onToggle}
    >
      <div className="flex h-full min-h-0 flex-col pb-3">
        <div className="shrink-0 px-3">
          <UploadDocumentForm
            workspaceId={workspaceId}
            buttonRef={uploadButtonRef}
          />

          <div
            role="group"
            aria-label="Filter documents"
            className="mt-3 flex items-center gap-0.5 rounded-md border border-border bg-background p-0.5"
          >
            <FilterLink href={documentsPath} active={!mine} label="All" />
            <FilterLink
              href={`${documentsPath}?mine=true`}
              active={mine}
              label="Mine"
            />
          </div>
        </div>

        {documents.length === 0 ? (
          <p className="mt-3 shrink-0 px-3 text-xs leading-5 text-muted">
            {mine
              ? "You haven't uploaded any documents in this workspace yet."
              : "No documents yet. Upload one to start chatting."}
          </p>
        ) : (
          <ul className={`${sidebarScroll} mt-3 max-h-[220px] space-y-0.5 px-2 pt-1 pb-2`}>
            {documents.map((document) => (
              <li
                key={document.id}
                className="group relative flex h-10 items-center gap-2 rounded-md px-1 transition-colors duration-150 hover:bg-surface"
              >
                <span
                  aria-hidden="true"
                  className="grid size-6 shrink-0 place-items-center rounded-md border border-border bg-elevated font-mono text-[10px] font-medium text-muted"
                >
                  {documentKind(document.filename)}
                </span>

                <Link
                  href={`${documentsPath}/documents/${document.id}`}
                  title={document.filename}
                  className="flex min-w-0 flex-1 items-center gap-2 rounded-sm"
                >
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                    {document.filename}
                  </span>
                  <span className="shrink-0 text-xs text-muted tabular-nums">
                    {formatBytes(document.size_bytes)}
                  </span>
                </Link>

                <div className="w-7 shrink-0">
                  {canManageDocument(myRole, userId, document) ? (
                    <div className="opacity-0 transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100 max-lg:opacity-100">
                      <DeleteDocumentButton
                        workspaceId={workspaceId}
                        documentId={document.id}
                        filename={document.filename}
                        variant="icon"
                        refreshOnDelete
                      />
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SidebarSection>
  );
}

function FilterLink({
  href,
  active,
  label,
}: {
  href: string;
  active: boolean;
  label: string;
}) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={active ? "page" : undefined}
      className={[
        "flex h-7 flex-1 items-center justify-center rounded text-xs font-medium transition-colors duration-150",
        active
          ? "bg-elevated text-foreground"
          : "text-muted hover:text-foreground",
      ].join(" ")}
    >
      {label}
    </Link>
  );
}
