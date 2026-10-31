import { apiErrorResponse, uploadDocument } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

export async function POST(
  request: Request,
  context: RouteContext<"/api/workspaces/[id]/documents">,
) {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { id } = await context.params;
  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) {
    return Response.json(
      { detail: "Choose a file to upload.", fields: [] },
      { status: 422 },
    );
  }

  try {
    const document = await uploadDocument(token, id, file);
    return Response.json(document, { status: 201 });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
