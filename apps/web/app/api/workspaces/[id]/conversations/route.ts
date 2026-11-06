import { apiErrorResponse, createConversation } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(
  request: Request,
  context: RouteContext<"/api/workspaces/[id]/conversations">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id } = await context.params;
  const body = await request.json().catch(() => null);
  const title =
    typeof body?.title === "string" && body.title.trim()
      ? body.title.trim()
      : undefined;

  try {
    const conversation = await createConversation(token, id, title);
    return Response.json(conversation, { status: 201 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
