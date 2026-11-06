import { apiErrorResponse, reindexDocument } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(
  _request: Request,
  context: RouteContext<"/api/workspaces/[id]/documents/[documentId]/reindex">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id, documentId } = await context.params;

  try {
    const result = await reindexDocument(token, id, documentId);
    return Response.json(result, { status: 202 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
