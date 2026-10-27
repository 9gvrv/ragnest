import { ApiError, login } from "@/lib/api";
import { safeNextPath } from "@/lib/next-path";
import { setSessionToken } from "@/lib/session";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const email = typeof body?.email === "string" ? body.email : "";
  const password = typeof body?.password === "string" ? body.password : "";
  // Only same-site paths survive: safeNextPath parses the value rather than
  // trusting a "/" prefix, so "/\evil.com" and friends fall back to "/".
  const redirect =
    safeNextPath(typeof body?.next === "string" ? body.next : null) ?? "/";

  try {
    const result = await login(email, password);
    await setSessionToken(result.access_token);
    return Response.json({ ok: true, redirect });
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json(
        { detail: error.message, fields: error.fields },
        { status: error.status === 0 ? 502 : error.status },
      );
    }
    return Response.json(
      { detail: "Something went wrong. Try again." },
      { status: 500 },
    );
  }
}
