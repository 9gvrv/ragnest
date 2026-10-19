import { cookies } from "next/headers";

export const SESSION_COOKIE = "ragnest_session";

/** The API issues 30-minute tokens with no refresh, so the cookie mirrors that. */
const SESSION_SECONDS = 30 * 60;

export async function setSessionToken(token: string) {
  const store = await cookies();
  store.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_SECONDS,
  });
}

export async function getSessionToken() {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

export async function clearSessionToken() {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
}
