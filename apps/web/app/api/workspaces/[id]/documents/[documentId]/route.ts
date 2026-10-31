import { apiErrorResponse, deleteDocument } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function DELETE(
  _request: Request,
  context: RouteContext<"/api/workspaces/[id]/documents/[documentId]">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id, documentId } = await context.params;

  try {
    await deleteDocument(token, id, documentId);
    return new Response(null, { status: 204 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
