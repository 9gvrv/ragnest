/**
 * Placeholder shapes for the chat list and message column. There is no chat
 * backend yet; these types exist so the UI can be wired up without reshaping
 * the components later.
 */
export type WorkspaceChat = {
  id: string;
  title: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};
