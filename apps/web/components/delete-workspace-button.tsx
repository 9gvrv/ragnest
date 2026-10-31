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
        window.location.assign("/workspaces");
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
        className="inline-flex h-9 items-center justify-center rounded-md border border-border px-4 text-sm font-medium text-danger transition-colors duration-150 hover:border-danger/60 hover:bg-danger/5 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending ? "Deleting…" : "Delete workspace"}
      </button>
      {failure ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {failure}
        </p>
      ) : null}
    </div>
  );
}
