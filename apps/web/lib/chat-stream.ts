import type { ApiCitation } from "@/lib/api";

export type ChatSourcesEvent = {
  user_message_id: string;
  assistant_message_id: string;
  sources: ApiCitation[];
  no_context: boolean;
};

export type ChatDoneEvent = {
  assistant_message_id: string;
  finish_reason: string;
  cited: number[];
};

export type ChatStreamEvent =
  | { type: "sources"; data: ChatSourcesEvent }
  | { type: "token"; data: { delta: string } }
  | { type: "done"; data: ChatDoneEvent }
  | { type: "error"; data: { detail: string } };

/**
 * Parse one SSE frame. The API emits `event: <name>` followed by a single
 * `data: <json>` line, but multi-line data is joined per the SSE spec.
 */
export function parseChatEvent(frame: string): ChatStreamEvent | null {
  let eventName = "";
  const dataLines: string[] = [];

  for (const rawLine of frame.split("\n")) {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (!eventName || dataLines.length === 0) return null;

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    return null;
  }
  if (typeof payload !== "object" || payload === null) return null;

  const data = payload as Record<string, unknown>;

  switch (eventName) {
    case "sources":
      if (
        typeof data.assistant_message_id !== "string" ||
        !Array.isArray(data.sources)
      ) {
        return null;
      }
      return {
        type: "sources",
        data: {
          user_message_id: String(data.user_message_id ?? ""),
          assistant_message_id: data.assistant_message_id,
          sources: data.sources as ApiCitation[],
          no_context: Boolean(data.no_context),
        },
      };
    case "token":
      return typeof data.delta === "string"
        ? { type: "token", data: { delta: data.delta } }
        : null;
    case "done":
      return typeof data.assistant_message_id === "string" &&
        typeof data.finish_reason === "string"
        ? {
            type: "done",
            data: {
              assistant_message_id: data.assistant_message_id,
              finish_reason: data.finish_reason,
              cited: Array.isArray(data.cited) ? (data.cited as number[]) : [],
            },
          }
        : null;
    case "error":
      return {
        type: "error",
        data: {
          detail:
            typeof data.detail === "string"
              ? data.detail
              : "The answer stopped early.",
        },
      };
    default:
      return null;
  }
}

/**
 * Read the proxy's SSE body incrementally and hand each known event to the
 * caller. Frames are separated by a blank line; a trailing frame is flushed.
 */
export async function readChatStream(
  response: Response,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error("The answer stream was empty.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function drain() {
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseChatEvent(frame);
      if (event) onEvent(event);
      boundary = buffer.indexOf("\n\n");
    }
  }

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      drain();
    }
    buffer += decoder.decode();
    const event = parseChatEvent(buffer.trim());
    if (event) onEvent(event);
  } finally {
    reader.releaseLock();
  }
}
