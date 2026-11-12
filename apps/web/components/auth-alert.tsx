const MESSAGES: Record<string, string> = {
  google_state: "That sign-in link expired. Try again.",
  google_unverified: "Google hasn't verified that email address.",
  google_conflict: "That email is already linked to another sign-in method.",
  google_denied: "Google sign-in was cancelled.",
  google_unconfigured: "Google sign-in isn't available right now.",
  google_failed:
    "Google sign-in didn't work. Try again, or use your email and password.",
};

/** Renders the API's redirect codes as one sentence, or nothing at all. */
export function AuthAlert({ code }: { code?: string }) {
  if (!code) return null;

  return (
    <p role="alert" className="mb-6 text-sm text-danger">
      {MESSAGES[code] ?? MESSAGES.google_failed}
    </p>
  );
}
