/**
 * A `next` value is only safe when it stays on this site. A prefix check alone
 * is not enough: browsers normalise `/\evil.com` and control characters into an
 * off-site URL, so parse the value and compare the origin.
 *
 * Returns a path on this site, or null when the value must be ignored.
 */
export function safeNextPath(raw: string | undefined | null): string | null {
  if (!raw || !raw.startsWith("/")) return null;
  // Backslashes and control characters are never part of a path we hand out,
  // and the URL parser would turn them into a host separator.
  if (/[\u0000-\u001f\u007f\\]/.test(raw)) return null;

  try {
    const base = "http://ragnest.invalid";
    const url = new URL(raw, base);
    if (url.origin !== base) return null;

    const path = `${url.pathname}${url.search}${url.hash}`;
    // A percent-encoded backslash is harmless in a path, but decoding it here
    // keeps every caller on the same invariant.
    const decoded = decodeURIComponent(path);
    if (/[\u0000-\u001f\u007f\\]/.test(decoded)) return null;

    return path;
  } catch {
    return null;
  }
}
