import { NextResponse } from "next/server";
import { ApiError, exchangeGoogleCode } from "@/lib/api";
import {
  clearGoogleOAuthCookie,
  googleOAuthConfigured,
  readGoogleOAuthCookie,
} from "@/lib/google-oauth";
import { safeNextPath } from "@/lib/next-path";
import { setSessionToken } from "@/lib/session";

/** Every failure lands on /login with a code the page can explain. */
function backToLogin(url: URL, error: string) {
  return NextResponse.redirect(new URL(`/login?error=${error}`, url));
}

/**
 * Step two: prove the callback belongs to the browser that started it, then
 * trade the code for a session. The API does the secret half.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const stored = await readGoogleOAuthCookie();
  // One attempt per cookie, whatever happens next.
  await clearGoogleOAuthCookie();

  if (!googleOAuthConfigured()) {
    return backToLogin(url, "google_unconfigured");
  }

  // Cancelling on Google's screen returns an error, not a code.
  const denied = url.searchParams.get("error");
  if (denied) {
    return backToLogin(
      url,
      denied === "access_denied" ? "google_denied" : "google_failed",
    );
  }

  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  if (!stored || !code || !state || state !== stored.state) {
    return backToLogin(url, "google_state");
  }

  try {
    const result = await exchangeGoogleCode(
      code,
      stored.verifier,
      process.env.GOOGLE_REDIRECT_URI ?? "",
    );
    await setSessionToken(result.access_token);
    return NextResponse.redirect(
      new URL(safeNextPath(stored.next) ?? "/workspaces", url),
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return backToLogin(url, "google_unverified");
    }
    if (error instanceof ApiError && error.status === 409) {
      return backToLogin(url, "google_conflict");
    }
    return backToLogin(url, "google_failed");
  }
}
