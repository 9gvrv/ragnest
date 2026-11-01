"use client";

import type { RefObject } from "react";
import { ChatComposer } from "@/components/workspace/chat-composer";
import type { ChatMessage } from "@/lib/chats";

type ChatAreaProps = {
  workspaceName: string;
  hasDocuments: boolean;
  documentNames: string[];
  messages: ChatMessage[];
  composerRef: RefObject<HTMLTextAreaElement | null>;
  onUploadRequest: () => void;
};

export function ChatArea({
  workspaceName,
  hasDocuments,
  documentNames,
  messages,
  composerRef,
  onUploadRequest,
}: ChatAreaProps) {
  function onSubmitQuestion(question: string) {
    // TODO: wire to backend
    void question;
  }

  if (messages.length === 0) {
    return (
      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="flex min-h-full flex-col items-center justify-center px-4 py-10 sm:px-6">
          <div className="w-full max-w-[780px]">
            <div className="mx-auto max-w-[620px] text-center">
              <h2 className="text-3xl font-semibold tracking-[-0.04em] text-balance text-foreground sm:text-4xl">
                What would you like to know about {workspaceName}?
              </h2>
              <p className="mt-3 text-sm leading-6 text-muted">
                {hasDocuments
                  ? "Ragnest answers only from the documents in this workspace."
                  : "Add a document in the sidebar to unlock the chat."}
              </p>
            </div>

            <div className="mt-8">
              <ChatComposer
                workspaceName={workspaceName}
                hasDocuments={hasDocuments}
                inputRef={composerRef}
                onSubmitQuestion={onSubmitQuestion}
                onUploadRequest={onUploadRequest}
              />
            </div>

            {hasDocuments ? (
              <ul
                aria-label="Documents in this workspace"
                className="mt-3 flex flex-wrap items-center justify-center gap-1.5"
              >
                {documentNames.slice(0, 3).map((name, index) => (
                  <li
                    key={`${name}-${index}`}
                    className="max-w-[180px] truncate rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-muted"
                  >
                    {name}
                  </li>
                ))}
                {documentNames.length > 3 ? (
                  <li className="rounded-full border border-border px-2.5 py-1 text-xs text-muted">
                    +{documentNames.length - 3} more
                  </li>
                ) : null}
              </ul>
            ) : null}
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <ol className="mx-auto flex w-full max-w-[780px] flex-col gap-6">
          {messages.map((message) => (
            <li
              key={message.id}
              className={
                message.role === "user"
                  ? "ml-auto max-w-[85%] rounded-xl border border-border bg-surface px-4 py-3"
                  : "max-w-[85%]"
              }
            >
              <p className="text-xs text-muted">
                {message.role === "user" ? "You" : "Ragnest"}
              </p>
              <p className="mt-1 text-sm leading-6 whitespace-pre-wrap text-foreground">
                {message.content}
              </p>
            </li>
          ))}
        </ol>
      </div>

      <div className="shrink-0 border-t border-border bg-background/80 px-4 py-3 backdrop-blur-sm sm:px-6">
        <div className="mx-auto w-full max-w-[780px]">
          <ChatComposer
            workspaceName={workspaceName}
            hasDocuments={hasDocuments}
            inputRef={composerRef}
            onSubmitQuestion={onSubmitQuestion}
            onUploadRequest={onUploadRequest}
          />
        </div>
      </div>
    </main>
  );
}
