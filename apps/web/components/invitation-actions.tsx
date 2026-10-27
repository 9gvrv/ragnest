"use client";

import { useState } from "react";
import { Button } from "@/components/button";

type Action = "accept" | "decline";

export function InvitationActions({ token }: { token: string }) {
  const [pending, setPending] = useState<Action | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  function signInAgain() {
    const next = encodeURIComponent("/invitations");
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${next}`);
  }

  async function run(action: Action) {
    setPending(action);
    setFailure(null);

    try {
      const response = await fetch(`/api/invitations/${token}/${action}`, {
        method: "POST",
      });

      if (response.status === 401) {
        signInAgain();
        return;
      }

      if (action === "accept" && response.ok) {
        const body: { workspace_id: string } = await response.json();
        // The workspace just appeared in this person's list; a full navigation
        // keeps the router from serving a pre-accept copy.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/workspaces/${body.workspace_id}`);
        return;
      }

      if (action === "decline" && response.status === 204) {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/invitations");
        return;
      }

      const body = await response.json().catch(() => null);
      setFailure(
        typeof body?.detail === "string"
          ? body.detail
          : "Something went wrong. Try again.",
      );
    } catch {
      setFailure("Can't reach the server. Try again.");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex items-center gap-5">
        <button
          type="button"
          onClick={() => run("decline")}
          disabled={pending !== null}
          className="text-[13px] text-muted underline-offset-4 hover:text-ink hover:underline disabled:opacity-60"
        >
          {pending === "decline" ? "Declining…" : "Decline"}
        </button>
        <Button
          type="button"
          pending={pending === "accept"}
          disabled={pending !== null}
          onClick={() => run("accept")}
        >
          Accept
        </Button>
      </div>
      {failure ? (
        <p role="alert" className="text-right text-[13px] text-danger">
          {failure}
        </p>
      ) : null}
    </div>
  );
}
