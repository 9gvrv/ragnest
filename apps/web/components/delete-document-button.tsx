"use client";

import { useState } from "react";
import { documentFailure } from "@/lib/documents";

export function DeleteDocumentButton({
  workspaceId,
  documentId,
  filename,
  backHref,
  align = "end",
}: {
  workspaceId: string;
  documentId: string;
  filename: string;
  /** Where to go after the row is gone; defaults to the current page. */
  backHref?: string;
  align?: "start" | "end";
}) {
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function remove() {
    const confirmed = window.confirm(
      `Delete "${filename}"? Its extracted text goes with it, and this can't be undone.`,
    );
    if (!confirmed) return;

    setPending(true);
    setFailure(null);

    try {
      const response = await fetch(
        `/api/workspaces/${workspaceId}/documents/${documentId}`,
        { method: "DELETE" },
      );

      if (response.status === 401) {
        const next = encodeURIComponent(
          window.location.pathname + window.location.search,
        );
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/login?next=${next}`);
        return;
      }

      if (response.status === 204) {
        // Full navigation so no cached document list survives the delete.
        window.location.assign(
          backHref ?? window.location.pathname + window.location.search,
        );
        return;
      }

      const body = await response.json().catch(() => null);
      setFailure(
        documentFailure(
          response.status,
          typeof body?.detail === "string" ? body.detail : null,
        ),
      );
    } catch {
      setFailure("Can't reach the server. Try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      className={[
        "flex flex-col gap-1",
        align === "end" ? "items-end" : "items-start",
      ].join(" ")}
    >
      <button
        type="button"
        onClick={remove}
        disabled={pending}
        aria-label={`Delete ${filename}`}
        className="text-sm text-muted transition-colors duration-150 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending ? "Deleting…" : "Delete"}
      </button>
      {failure ? (
        <p
          role="alert"
          className={[
            "text-xs text-danger",
            align === "end" ? "text-right" : "text-left",
          ].join(" ")}
        >
          {failure}
        </p>
      ) : null}
    </div>
  );
}
