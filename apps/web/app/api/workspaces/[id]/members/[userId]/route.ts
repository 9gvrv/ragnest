import { apiErrorResponse, removeMember } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function DELETE(
  _request: Request,
  context: RouteContext<"/api/workspaces/[id]/members/[userId]">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id, userId } = await context.params;

  try {
    await removeMember(token, id, userId);
    return new Response(null, { status: 204 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
