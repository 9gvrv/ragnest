import { acceptInvitation, apiErrorResponse } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(
  _request: Request,
  context: RouteContext<"/api/invitations/[token]/accept">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { token: invitationToken } = await context.params;

  try {
    const accepted = await acceptInvitation(token, invitationToken);
    return Response.json(accepted);
  } catch (error) {
    return apiErrorResponse(error);
  }
}
