/**
 * Reads the expiry out of a JWT for display only. The API is still the thing
 * that decides whether a token is valid — this never gates access on its own.
 */
export function tokenExpiry(token: string): Date | null {
  const [, payload] = token.split(".");
  if (!payload) return null;

  try {
    const json = JSON.parse(
      Buffer.from(payload.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString(),
    ) as { exp?: unknown };
    return typeof json.exp === "number" ? new Date(json.exp * 1000) : null;
  } catch {
    return null;
  }
}
