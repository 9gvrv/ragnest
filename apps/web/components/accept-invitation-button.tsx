"use client";

import { useState } from "react";
import { Button } from "@/components/button";

type Problem =
  | { kind: "mismatch" }
  | { kind: "dead"; detail: string }
  | { kind: "other"; detail: string };

export function AcceptInvitationButton({
  token,
  email,
}: {
  token: string;
  email: string;
}) {
  const [pending, setPending] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  const next = encodeURIComponent(`/invite/${token}`);

  async function switchAccount() {
    setSwitching(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // If the call fails the cookie survives; the person can still sign out
      // from /account. Nothing else to do here.
    }
    // The cookie just changed (or should have); a full navigation drops the
    // router cache built for the old session.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${next}`);
  }

  async function accept() {
    setPending(true);
    setProblem(null);

    try {
      const response = await fetch(`/api/invitations/${token}/accept`, {
        method: "POST",
      });

      if (response.status === 401) {
        // The session ended while this page was open; sign in and come back.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/login?next=${next}`);
        return;
      }

      if (response.ok) {
        const body: { workspace_id: string } = await response.json();
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/workspaces/${body.workspace_id}`);
        return;
      }

      if (response.status === 403) {
        setProblem({ kind: "mismatch" });
        return;
      }

      const body = await response.json().catch(() => null);
      const detail =
        typeof body?.detail === "string"
          ? body.detail
          : "Something went wrong. Try again.";

      if (
        response.status === 400 ||
        response.status === 404 ||
        response.status === 410
      ) {
        setProblem({ kind: "dead", detail });
        return;
      }

      setProblem({ kind: "other", detail });
    } catch {
      setProblem({
        kind: "other",
        detail: "Can't reach the server. Try again.",
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <div>
      <Button type="button" onClick={accept} pending={pending}>
        Accept invitation
      </Button>

      {problem ? (
        <div role="alert" className="mt-4 max-w-[55ch] text-[13px] text-danger">
          {problem.kind === "mismatch" ? (
            <>
              <p>
                This invitation was sent to {email}. Sign in with that account.
              </p>
              <button
                type="button"
                onClick={switchAccount}
                disabled={switching}
                className="mt-2 text-left text-action underline-offset-4 hover:underline disabled:opacity-60"
              >
                {switching
                  ? "Signing out…"
                  : `Sign out and sign in as ${email}`}
              </button>
            </>
          ) : problem.kind === "dead" ? (
            <p>
              {problem.detail} Ask whoever invited you for a new link.
            </p>
          ) : (
            <p>{problem.detail}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
