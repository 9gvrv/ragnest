"use client";

import { useState } from "react";
import { UserMinusIcon } from "@/components/workspace/icons";

export function RemoveMemberButton({
  workspaceId,
  userId,
  email,
  variant = "text",
}: {
  workspaceId: string;
  userId: string;
  email: string;
  variant?: "text" | "icon";
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
    <div className="relative flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={remove}
        disabled={pending}
        aria-label={`Remove ${email} from this workspace`}
        className={
          variant === "icon"
            ? "grid size-7 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-elevated hover:text-danger disabled:opacity-50"
            : "text-sm text-muted transition-colors duration-150 hover:text-danger disabled:opacity-50"
        }
      >
        {variant === "icon" ? (
          <UserMinusIcon className="size-3.5" />
        ) : pending ? (
          "Removing…"
        ) : (
          "Remove"
        )}
      </button>
      {failure ? (
        <span
          role="alert"
          className={
            variant === "icon"
              ? "absolute top-full right-0 z-10 mt-1 w-40 rounded-md border border-border bg-background p-2 text-left text-xs text-danger"
              : "text-right text-xs text-danger"
          }
        >
          {failure}
        </span>
      ) : null}
    </div>
  );
}
