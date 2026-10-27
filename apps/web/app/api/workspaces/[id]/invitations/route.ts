import { apiErrorResponse, createInvitation } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(
  request: Request,
  context: RouteContext<"/api/workspaces/[id]/invitations">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id } = await context.params;
  const body = await request.json().catch(() => null);
  const email = typeof body?.email === "string" ? body.email : "";
  const role = body?.role === "admin" ? "admin" : "member";

  try {
    const invitation = await createInvitation(token, id, email, role);
    return Response.json(invitation, { status: 201 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
