import { createHash, randomBytes } from "node:crypto";
import { cookies } from "next/headers";

export const GOOGLE_COOKIE = "ragnest_google";

const AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth";

/** Long enough to pick an account, short enough to go stale. */
const COOKIE_SECONDS = 10 * 60;

/** What the start route hands the callback route through the cookie. */
export type GoogleOAuthState = {
  state: string;
  verifier: string;
  next: string;
};

/** The button and both routes stay dormant unless the client is configured. */
export function googleOAuthConfigured() {
  return Boolean(
    process.env.GOOGLE_CLIENT_ID?.trim() &&
      process.env.GOOGLE_REDIRECT_URI?.trim(),
  );
}

function base64url(buffer: Buffer) {
  return buffer.toString("base64url");
}

export function randomToken(bytes = 32) {
  return base64url(randomBytes(bytes));
}

/** PKCE S256: the challenge is the SHA-256 of the verifier, base64url. */
export function codeChallengeFor(verifier: string) {
  return base64url(createHash("sha256").update(verifier).digest());
}

export function buildAuthorizeUrl(state: GoogleOAuthState) {
  const params = new URLSearchParams({
    client_id: process.env.GOOGLE_CLIENT_ID ?? "",
    redirect_uri: process.env.GOOGLE_REDIRECT_URI ?? "",
    response_type: "code",
    scope: "openid email",
    state: state.state,
    code_challenge: codeChallengeFor(state.verifier),
    code_challenge_method: "S256",
    access_type: "online",
    prompt: "select_account",
  });
  return `${AUTHORIZE_URL}?${params.toString()}`;
}

export async function setGoogleOAuthCookie(value: GoogleOAuthState) {
  const store = await cookies();
  store.set(GOOGLE_COOKIE, JSON.stringify(value), {
    httpOnly: true,
    // "lax" is required: Google returns with a cross-site top-level GET, and
    // "strict" would drop the cookie exactly when we need it.
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    // The default path, deliberately: cookies().delete() cannot target a
    // narrower path, and a leftover cookie would fail the state check later.
    path: "/",
    maxAge: COOKIE_SECONDS,
  });
}

export async function readGoogleOAuthCookie(): Promise<GoogleOAuthState | null> {
  const store = await cookies();
  const raw = store.get(GOOGLE_COOKIE)?.value;
  if (!raw) return null;

  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const { state, verifier, next } = parsed as Partial<GoogleOAuthState>;
    if (
      typeof state !== "string" ||
      typeof verifier !== "string" ||
      typeof next !== "string"
    ) {
      return null;
    }
    return { state, verifier, next };
  } catch {
    return null;
  }
}

export async function clearGoogleOAuthCookie() {
  const store = await cookies();
  store.delete(GOOGLE_COOKIE);
}
