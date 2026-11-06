"use client";

import Link from "next/link";
import { DeleteConversationButton } from "@/components/delete-conversation-button";
import { MessageIcon, PlusIcon } from "@/components/workspace/icons";
import { SectionCount } from "@/components/workspace/sidebar-section";
import { sidebarScroll } from "@/components/workspace/sidebar-scroll";
import type { ApiConversation } from "@/lib/api";
import { parseApiDate } from "@/lib/dates";

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
});

type ChatsSectionProps = {
  workspaceId: string;
  chats: ApiConversation[];
  selectedChatId: string | null;
  onNewChat: () => void;
  onDeleted: (conversationId: string) => void;
};

export function ChatsSection({
  workspaceId,
  chats,
  selectedChatId,
  onNewChat,
  onDeleted,
}: ChatsSectionProps) {
  return (
    <section
      aria-labelledby="chats-heading"
      className="flex min-h-0 flex-[1_1_160px] flex-col"
    >
      <div className="flex h-8 shrink-0 items-center gap-2 px-3">
        <span aria-hidden="true" className="size-3.5 shrink-0" />
        <h2
          id="chats-heading"
          className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground"
        >
          Chats
        </h2>
        <SectionCount count={chats.length} />
      </div>

      <div className="shrink-0 px-3 pt-2">
        <Link
          href={`/workspaces/${workspaceId}`}
          onClick={onNewChat}
          className="flex h-12 w-full items-center gap-2 rounded-lg border border-border bg-background px-2.5 text-left text-sm font-medium text-foreground transition-colors duration-150 hover:border-control hover:bg-surface"
        >
          <span
            aria-hidden="true"
            className="grid size-7 shrink-0 place-items-center rounded-md border border-border bg-elevated text-muted"
          >
            <PlusIcon className="size-3.5" />
          </span>
          New chat
        </Link>
      </div>

      <div className={`${sidebarScroll} flex-1 px-2 py-2`}>
        {chats.length === 0 ? (
          <p className="px-1 py-2 text-xs leading-5 text-muted">
            No chats yet. Ask a question to start one.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {chats.map((chat) => {
              const active = chat.id === selectedChatId;
              return (
                <li
                  key={chat.id}
                  className={[
                    "group flex items-center gap-0.5 rounded-md pr-1 transition-colors duration-150",
                    active ? "bg-surface" : "hover:bg-surface",
                  ].join(" ")}
                >
                  <Link
                    href={`/workspaces/${workspaceId}?chat=${chat.id}`}
                    aria-current={active ? "page" : undefined}
                    className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-md px-1 text-left"
                  >
                    <MessageIcon
                      className={
                        active
                          ? "size-3.5 shrink-0 text-foreground"
                          : "size-3.5 shrink-0 text-muted"
                      }
                    />
                    <span
                      className={
                        active
                          ? "min-w-0 flex-1 truncate text-sm font-medium text-foreground"
                          : "min-w-0 flex-1 truncate text-sm text-foreground"
                      }
                    >
                      {chat.title}
                    </span>
                    <span className="shrink-0 text-xs text-muted tabular-nums">
                      {dateFormat.format(parseApiDate(chat.updated_at))}
                    </span>
                  </Link>

                  <span className="w-7 shrink-0 opacity-0 transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100 max-lg:opacity-100">
                    <DeleteConversationButton
                      workspaceId={workspaceId}
                      conversationId={chat.id}
                      title={chat.title}
                      active={active}
                      onDeleted={onDeleted}
                    />
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
