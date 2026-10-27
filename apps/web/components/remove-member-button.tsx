"use client";

import { useState } from "react";

export function RemoveMemberButton({
  workspaceId,
  userId,
  email,
}: {
  workspaceId: string;
  userId: string;
  email: string;
}) {
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function remove() {
    setPending(true);
    setFailure(null);

    try {
      const response = await fetch(
        `/api/workspaces/${workspaceId}/members/${userId}`,
        { method: "DELETE" },
      );

      if (response.status === 401) {
        const next = encodeURIComponent(window.location.pathname);
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/login?next=${next}`);
        return;
      }

      if (response.status === 204) {
        // The member list just changed; a full navigation keeps no stale copy.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/workspaces/${workspaceId}`);
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
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={remove}
        disabled={pending}
        aria-label={`Remove ${email} from this workspace`}
        className="text-[13px] text-danger underline-offset-4 hover:underline disabled:opacity-60"
      >
        {pending ? "Removing…" : "Remove"}
      </button>
      {failure ? (
        <span role="alert" className="text-right text-[12px] text-danger">
          {failure}
        </span>
      ) : null}
    </div>
  );
}
