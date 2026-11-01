"use client";

import { MessageIcon, PlusIcon } from "@/components/workspace/icons";
import type { WorkspaceChat } from "@/lib/chats";
import { parseApiDate } from "@/lib/dates";

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
});

type ChatsSectionProps = {
  chats: WorkspaceChat[];
  onNewChat: () => void;
  onSelectChat?: (chat: WorkspaceChat) => void;
};

export function ChatsSection({
  chats,
  onNewChat,
  onSelectChat,
}: ChatsSectionProps) {
  return (
    <section
      aria-labelledby="chats-heading"
      className="flex min-h-0 flex-[1_1_160px] flex-col"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 px-3 pt-3">
        <h2
          id="chats-heading"
          className="text-sm font-semibold text-foreground"
        >
          Chats
        </h2>
        <span className="font-mono text-xs text-muted tabular-nums">
          {chats.length}
        </span>
      </div>

      <div className="shrink-0 px-3 pt-2">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-lg border border-border bg-background px-2.5 py-2 text-left text-sm font-medium text-foreground transition-colors duration-150 hover:border-control hover:bg-surface"
        >
          <span
            aria-hidden="true"
            className="grid size-7 shrink-0 place-items-center rounded-md border border-border bg-elevated text-muted"
          >
            <PlusIcon className="size-3.5" />
          </span>
          New chat
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {chats.length === 0 ? (
          <p className="px-1 py-2 text-xs leading-5 text-muted">
            No chats yet. Ask a question to start one.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {chats.map((chat) => (
              <li key={chat.id}>
                <button
                  type="button"
                  onClick={() => onSelectChat?.(chat)}
                  className="group flex w-full items-center gap-2 rounded-md px-1.5 py-1.5 text-left transition-colors duration-150 hover:bg-surface"
                >
                  <MessageIcon className="size-3.5 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                    {chat.title}
                  </span>
                  <span className="shrink-0 text-xs text-muted tabular-nums">
                    {dateFormat.format(parseApiDate(chat.updated_at))}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
