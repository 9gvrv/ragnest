"use client";

import { useState } from "react";

export function SignOut() {
  const [pending, setPending] = useState(false);

  async function signOut() {
    setPending(true);
    await fetch("/api/auth/logout", { method: "POST" });
    // Same reason as sign-in: drop prefetched payloads built for the old session.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/login");
  }

  return (
    <button
      type="button"
      onClick={signOut}
      disabled={pending}
      className="text-sm text-muted transition-colors duration-150 hover:text-foreground disabled:opacity-50"
    >
      {pending ? "Signing out…" : "Sign out"}
    </button>
  );
}
