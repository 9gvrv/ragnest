"use client";

import Link from "next/link";
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
  const [problem, setProblem] = useState<Problem | null>(null);

  const next = encodeURIComponent(`/invite/${token}`);

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
              <p>This invitation was sent to {email}. Sign in with that account.</p>
              <Link
                href={`/login?next=${next}`}
                className="mt-2 inline-block text-action underline-offset-4 hover:underline"
              >
                Sign in with {email}
              </Link>
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
