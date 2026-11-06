import { apiErrorResponse, deleteConversation } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function DELETE(
  _request: Request,
  context: RouteContext<"/api/workspaces/[id]/conversations/[conversationId]">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id, conversationId } = await context.params;

  try {
    await deleteConversation(token, id, conversationId);
    return new Response(null, { status: 204 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
