import { NextResponse } from "next/server";
import {
  buildAuthorizeUrl,
  googleOAuthConfigured,
  randomToken,
  setGoogleOAuthCookie,
} from "@/lib/google-oauth";
import { safeNextPath } from "@/lib/next-path";

/**
 * Step one of Google sign-in: mint state + PKCE, park them in an httpOnly
 * cookie, and hand the browser to Google. Nothing secret leaves this server.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);

  if (!googleOAuthConfigured()) {
    return NextResponse.redirect(
      new URL("/login?error=google_unconfigured", url),
    );
  }

  const state = {
    state: randomToken(),
    verifier: randomToken(48),
    // The callback is a fresh request; the path a person wanted must survive it.
    next: safeNextPath(url.searchParams.get("next")) ?? "/workspaces",
  };

  await setGoogleOAuthCookie(state);

  return NextResponse.redirect(buildAuthorizeUrl(state));
}
