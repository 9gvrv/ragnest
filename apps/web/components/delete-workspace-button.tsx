"use client";

import { useState } from "react";

export function DeleteWorkspaceButton({
  workspaceId,
  workspaceName,
}: {
  workspaceId: string;
  workspaceName: string;
}) {
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function remove() {
    const confirmed = window.confirm(
      `Delete "${workspaceName}"? Its documents and members go with it, and this can't be undone.`,
    );
    if (!confirmed) return;

    setPending(true);
    setFailure(null);

    try {
      const response = await fetch(`/api/workspaces/${workspaceId}`, {
        method: "DELETE",
      });

      if (response.status === 401) {
        const next = encodeURIComponent(window.location.pathname);
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/login?next=${next}`);
        return;
      }

      if (response.status === 204) {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/");
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
    <div>
      <button
        type="button"
        onClick={remove}
        disabled={pending}
        className="rounded-[3px] border border-rule px-4 py-2 text-[15px] text-danger transition-colors hover:border-danger disabled:opacity-60"
      >
        {pending ? "Deleting…" : "Delete workspace"}
      </button>
      {failure ? (
        <p role="alert" className="mt-2 text-[13px] text-danger">
          {failure}
        </p>
      ) : null}
    </div>
  );
}
