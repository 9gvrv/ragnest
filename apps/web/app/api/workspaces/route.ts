import {
  apiErrorResponse,
  createWorkspace,
} from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(request: Request) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const body = await request.json().catch(() => null);
  const name = typeof body?.name === "string" ? body.name : "";

  try {
    const workspace = await createWorkspace(token, name);
    return Response.json(workspace, { status: 201 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
