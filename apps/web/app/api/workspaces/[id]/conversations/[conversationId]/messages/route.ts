import { apiErrorResponse, streamConversationMessage } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

const STREAM_HEADERS = {
  "Content-Type": "text/event-stream; charset=utf-8",
  "Cache-Control": "no-cache, no-transform",
  "X-Accel-Buffering": "no",
};

export async function POST(
  request: Request,
  context: RouteContext<"/api/workspaces/[id]/conversations/[conversationId]/messages">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id, conversationId } = await context.params;
  const body = await request.json().catch(() => null);
  const content = typeof body?.content === "string" ? body.content.trim() : "";
  if (!content) {
    return Response.json(
      { detail: "Ask a question first.", fields: [] },
      { status: 422 },
    );
  }

  try {
    const upstream = await streamConversationMessage(
      token,
      id,
      conversationId,
      content,
    );

    // Pre-stream failures are ordinary JSON. Forward the API's status and body
    // so the client can show its exact message.
    if (!upstream.ok) {
      const payload = await upstream.json().catch(() => null);
      return Response.json(
        payload ?? { detail: "Something went wrong. Try again." },
        { status: upstream.status },
      );
    }

    if (!upstream.body) {
      return Response.json(
        { detail: "The answer stream was empty." },
        { status: 502 },
      );
    }

    // Hand the upstream ReadableStream straight through: no buffering.
    return new Response(upstream.body, {
      status: 200,
      headers: STREAM_HEADERS,
    });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
