"use client";

import { useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { ChatComposer } from "@/components/workspace/chat-composer";
import {
  ChatMessage,
  type ChatUiMessage,
} from "@/components/workspace/chat-message";
import { readChatStream } from "@/lib/chat-stream";
import type { ApiConversation, ApiMessage } from "@/lib/api";

type ChatAreaProps = {
  workspaceId: string;
  workspaceName: string;
  hasDocuments: boolean;
  hasAnyDocuments: boolean;
  documentsIndexing: boolean;
  documentNames: string[];
  initialConversationId: string | null;
  initialMessages: ApiMessage[];
  composerRef: RefObject<HTMLTextAreaElement | null>;
  onUploadRequest: () => void;
  onConversationCreated: (conversation: ApiConversation) => void;
  onConversationTitled: (conversationId: string, title: string) => void;
};

function toUiMessage(message: ApiMessage): ChatUiMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations ?? [],
    finishReason: message.finish_reason,
    streaming: false,
  };
}

function chatFailure(status: number, detail?: string | null) {
  switch (status) {
    case 401:
      return "Your session ended. Sign in again to continue.";
    case 404:
      return "This chat no longer exists. Start a new one.";
    case 422:
      return detail ?? "That question couldn't be sent.";
    case 429:
      return "The answer model is busy. Try again in a moment.";
    case 503:
      return "The answer model is unavailable right now.";
    default:
      return detail ?? "Something went wrong. Try again.";
  }
}

function signInAgain() {
  const next = encodeURIComponent(
    window.location.pathname + window.location.search,
  );
  // The session ended mid-answer; resume here after signing in.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${next}`);
}

export function ChatArea({
  workspaceId,
  workspaceName,
  hasDocuments,
  hasAnyDocuments,
  documentsIndexing,
  documentNames,
  initialConversationId,
  initialMessages,
  composerRef,
  onUploadRequest,
  onConversationCreated,
  onConversationTitled,
}: ChatAreaProps) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatUiMessage[]>(() =>
    initialMessages.map(toUiMessage),
  );
  const [streaming, setStreaming] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const conversationIdRef = useRef(initialConversationId);
  const streamingRef = useRef(false);
  const createdHereRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  useEffect(() => {
    if (!stickRef.current) return;
    const element = listRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages]);

  function onListScroll() {
    const element = listRef.current;
    if (!element) return;
    stickRef.current =
      element.scrollHeight - element.scrollTop - element.clientHeight < 96;
  }

  function stop() {
    abortRef.current?.abort();
  }

  async function send(question: string) {
    const content = question.trim();
    if (!content || streamingRef.current) return;

    streamingRef.current = true;
    setStreaming(true);
    setFailure(null);

    const stamp = Date.now();
    const userTempId = `user-${stamp}`;
    const assistantPlaceholderId = `assistant-${stamp}`;
    let assistantId = assistantPlaceholderId;
    let navigatingAway = false;

    setMessages((current) => [
      ...current,
      {
        id: userTempId,
        role: "user",
        content,
        citations: [],
        finishReason: null,
        streaming: false,
      },
      {
        id: assistantPlaceholderId,
        role: "assistant",
        content: "",
        citations: [],
        finishReason: null,
        streaming: true,
      },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      let conversationId = conversationIdRef.current;
      if (!conversationId) {
        const created = await fetch(
          `/api/workspaces/${workspaceId}/conversations`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}",
          },
        );

        if (created.status === 401) {
          navigatingAway = true;
          signInAgain();
          return;
        }
        if (!created.ok) {
          const body = await created.json().catch(() => null);
          setFailure(
            chatFailure(
              created.status,
              typeof body?.detail === "string" ? body.detail : null,
            ),
          );
          setMessages((current) =>
            current.filter((message) => message.id !== assistantPlaceholderId),
          );
          return;
        }

        const conversation = (await created.json()) as ApiConversation;
        conversationId = conversation.id;
        conversationIdRef.current = conversation.id;
        createdHereRef.current = true;
        onConversationCreated(conversation);
      }

      const response = await fetch(
        `/api/workspaces/${workspaceId}/conversations/${conversationId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
          signal: controller.signal,
        },
      );

      if (response.status === 401) {
        navigatingAway = true;
        signInAgain();
        return;
      }

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setFailure(
          chatFailure(
            response.status,
            typeof body?.detail === "string" ? body.detail : null,
          ),
        );
        setMessages((current) =>
          current.filter((message) => message.id !== assistantPlaceholderId),
        );
        return;
      }

      await readChatStream(response, (event) => {
        switch (event.type) {
          case "sources": {
            assistantId = event.data.assistant_message_id;
            const sources = event.data.sources;
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantPlaceholderId
                  ? { ...message, id: assistantId, citations: sources }
                  : message,
              ),
            );
            break;
          }
          case "token": {
            const delta = event.data.delta;
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + delta }
                  : message,
              ),
            );
            break;
          }
          case "done": {
            assistantId = event.data.assistant_message_id;
            const finishReason = event.data.finish_reason;
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId || message.id === assistantPlaceholderId
                  ? {
                      ...message,
                      id: assistantId,
                      finishReason,
                      streaming: false,
                    }
                  : message,
              ),
            );
            if (createdHereRef.current && conversationIdRef.current) {
              // Mirror the API's titling rule so the sidebar and topbar update
              // without waiting for a server refresh.
              onConversationTitled(
                conversationIdRef.current,
                content.replace(/\s+/g, " ").slice(0, 80),
              );
            }
            break;
          }
          case "error": {
            setFailure("The answer stopped early. Try again.");
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, streaming: false }
                  : message,
              ),
            );
            break;
          }
        }
      });

      setMessages((current) =>
        current.map((message) =>
          message.streaming ? { ...message, streaming: false } : message,
        ),
      );
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, finishReason: "cancelled", streaming: false }
              : message,
          ),
        );
      } else {
        setFailure("Can't reach the server. Try again.");
        setMessages((current) =>
          current.filter((message) => message.id !== assistantPlaceholderId),
        );
      }
    } finally {
      streamingRef.current = false;
      setStreaming(false);
      abortRef.current = null;
      if (
        !navigatingAway &&
        createdHereRef.current &&
        conversationIdRef.current
      ) {
        createdHereRef.current = false;
        // Sync the router state with the new chat only after the stream has
        // settled, so a refresh cannot tear down an in-flight answer.
        router.replace(
          `/workspaces/${workspaceId}?chat=${conversationIdRef.current}`,
          { scroll: false },
        );
      }
    }
  }

  const errorAlert = failure ? (
    <p
      role="alert"
      className="rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-sm leading-6 text-danger"
    >
      {failure}
    </p>
  ) : null;

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
                  : !hasAnyDocuments
                    ? "Add a document in the sidebar to unlock the chat."
                    : documentsIndexing
                      ? "Your documents are still indexing. Chat unlocks when the first one is ready."
                      : "A document needs to finish indexing. Retry it in the sidebar to unlock the chat."}
              </p>
            </div>

            <div className="mt-8 space-y-3">
              {errorAlert}
              <ChatComposer
                workspaceName={workspaceName}
                hasDocuments={hasDocuments}
                hasAnyDocuments={hasAnyDocuments}
                documentsIndexing={documentsIndexing}
                streaming={streaming}
                inputRef={composerRef}
                onSubmitQuestion={(question) => void send(question)}
                onStop={stop}
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
      <div
        ref={listRef}
        onScroll={onListScroll}
        className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6"
      >
        <ol className="mx-auto flex w-full max-w-[780px] flex-col gap-6">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
        </ol>
      </div>

      <div className="shrink-0 border-t border-border bg-background/80 px-4 py-3 backdrop-blur-sm sm:px-6">
        <div className="mx-auto w-full max-w-[780px] space-y-2">
          {errorAlert}
          <ChatComposer
            workspaceName={workspaceName}
            hasDocuments={hasDocuments}
            hasAnyDocuments={hasAnyDocuments}
            documentsIndexing={documentsIndexing}
            streaming={streaming}
            inputRef={composerRef}
            onSubmitQuestion={(question) => void send(question)}
            onStop={stop}
            onUploadRequest={onUploadRequest}
          />
        </div>
      </div>
    </main>
  );
}
