import { apiErrorResponse, declineInvitation } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(
  _request: Request,
  context: RouteContext<"/api/invitations/[token]/decline">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { token: invitationToken } = await context.params;

  try {
    await declineInvitation(token, invitationToken);
    return new Response(null, { status: 204 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
