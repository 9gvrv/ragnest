import { apiErrorResponse, checkInvitationEmail } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(
  request: Request,
  context: RouteContext<"/api/workspaces/[id]/invitations/check">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id } = await context.params;
  const body = await request.json().catch(() => null);
  const email = typeof body?.email === "string" ? body.email : "";

  try {
    const result = await checkInvitationEmail(token, id, email);
    return Response.json(result);
  } catch (error) {
    return apiErrorResponse(error);
  }
}
