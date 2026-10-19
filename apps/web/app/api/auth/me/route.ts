import { ApiError, getMe } from "@/lib/api";
import { clearSessionToken, getSessionToken } from "@/lib/session";

export async function GET() {
  const token = await getSessionToken();
  if (!token) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  try {
    const user = await getMe(token);
    return Response.json({ user });
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401) await clearSessionToken();
      return Response.json(
        { detail: error.message },
        { status: error.status === 0 ? 502 : error.status },
      );
    }
    return Response.json(
      { detail: "Something went wrong. Try again." },
      { status: 500 },
    );
  }
}
