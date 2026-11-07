"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { RetryIcon } from "@/components/workspace/icons";
import { documentFailure } from "@/lib/documents";

export function ReindexDocumentButton({
  workspaceId,
  documentId,
  filename,
}: {
  workspaceId: string;
  documentId: string;
  filename: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function reindex() {
    setPending(true);
    setFailure(null);

    try {
      const response = await fetch(
        `/api/workspaces/${workspaceId}/documents/${documentId}/reindex`,
        { method: "POST" },
      );

      if (response.status === 401) {
        const next = encodeURIComponent(
          window.location.pathname + window.location.search,
        );
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/login?next=${next}`);
        return;
      }

      if (response.status === 202) {
        router.refresh();
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
    <span className="flex flex-col items-end">
      <button
        type="button"
        onClick={reindex}
        disabled={pending}
        aria-label={`Retry indexing ${filename}`}
        title={failure ?? `Retry indexing ${filename}`}
        className="grid size-7 place-items-center rounded-md text-muted transition-colors duration-150 hover:bg-elevated hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RetryIcon className={pending ? "size-3.5 animate-spin" : "size-3.5"} />
      </button>
      {failure ? (
        <span role="alert" className="sr-only">
          {failure}
        </span>
      ) : null}
    </span>
  );
}
