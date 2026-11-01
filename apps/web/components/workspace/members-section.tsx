"use client";

import { useRef } from "react";
import { InviteForm } from "@/components/invite-form";
import { RemoveMemberButton } from "@/components/remove-member-button";
import { SidebarSection } from "@/components/workspace/sidebar-section";
import { sidebarScroll } from "@/components/workspace/sidebar-scroll";
import { UserPlusIcon, XIcon } from "@/components/workspace/icons";
import type { ApiMember, ApiRole, ApiUser } from "@/lib/api";
import { canRemoveMember, initialsFromEmail } from "@/lib/workspace";

type MembersSectionProps = {
  workspaceId: string;
  members: ApiMember[];
  me: ApiUser;
  myRole: ApiRole;
  open: boolean;
  onToggle: () => void;
};

export function MembersSection({
  workspaceId,
  members,
  me,
  myRole,
  open,
  onToggle,
}: MembersSectionProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const canInvite = myRole === "creator" || myRole === "admin";

  return (
    <SidebarSection
      title="Members"
      count={members.length}
      open={open}
      onToggle={onToggle}
    >
      <div className="flex h-full min-h-0 flex-col pb-3">
        {canInvite ? (
          <div className="shrink-0 px-3">
            <button
              type="button"
              onClick={() => dialogRef.current?.showModal()}
              className="flex h-12 w-full items-center gap-2 rounded-lg border border-border bg-background px-2.5 text-left text-sm font-medium text-foreground transition-colors duration-150 hover:border-control hover:bg-surface"
            >
              <span
                aria-hidden="true"
                className="grid size-7 shrink-0 place-items-center rounded-md border border-border bg-elevated text-muted"
              >
                <UserPlusIcon className="size-3.5" />
              </span>
              Invite member
            </button>
          </div>
        ) : null}

        <ul
          className={`${sidebarScroll} mt-3 max-h-[220px] space-y-0.5 px-2 py-1`}
        >
          {members.map((member) => {
            const isMe = member.user_id === me.id;
            return (
              <li
                key={member.user_id}
                className="group relative flex items-center gap-2 rounded-md px-1.5 py-1.5 transition-colors duration-150 hover:bg-surface"
              >
                <span
                  aria-hidden="true"
                  className="grid size-7 shrink-0 place-items-center rounded-full border border-border bg-elevated text-[10px] font-semibold text-muted"
                >
                  {initialsFromEmail(member.email)}
                </span>

                <div className="min-w-0 flex-1">
                  <p className="flex min-w-0 items-center gap-1.5">
                    <span className="truncate text-sm text-foreground">
                      {member.email}
                    </span>
                    {isMe ? (
                      <span className="shrink-0 rounded-full border border-border px-1.5 py-0.5 text-[10px] leading-none text-muted">
                        you
                      </span>
                    ) : null}
                  </p>
                  <span className="mt-1 inline-flex rounded border border-border bg-foreground/5 px-1.5 py-0.5 font-mono text-[10px] leading-none text-muted">
                    {member.role}
                  </span>
                </div>

                {canRemoveMember(myRole, me.id, member) ? (
                  <div className="shrink-0 opacity-0 transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100 max-lg:opacity-100">
                    <RemoveMemberButton
                      workspaceId={workspaceId}
                      userId={member.user_id}
                      email={member.email}
                      variant="icon"
                    />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>

      <dialog
        ref={dialogRef}
        aria-labelledby="invite-dialog-title"
        onClick={(event) => {
          if (event.target === event.currentTarget) {
            event.currentTarget.close();
          }
        }}
        className="m-auto max-h-[85dvh] w-[min(92vw,420px)] overflow-y-auto rounded-xl border border-border bg-background p-5 text-foreground backdrop:bg-background/70"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2
              id="invite-dialog-title"
              className="text-base font-semibold tracking-tight text-foreground"
            >
              Invite a member
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              Ragnest doesn&apos;t send email yet. Create a link and send it
              yourself.
            </p>
          </div>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            aria-label="Close invite dialog"
            className="grid size-8 shrink-0 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground"
          >
            <XIcon className="size-4" />
          </button>
        </div>

        <div className="mt-5">
          <InviteForm workspaceId={workspaceId} />
        </div>
      </dialog>
    </SidebarSection>
  );
}
