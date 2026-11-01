"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type DragEvent, type RefObject } from "react";
import { UploadIcon } from "@/components/workspace/icons";
import {
  MAX_DOCUMENT_BYTES,
  documentFailure,
  formatBytes,
  isSupportedDocument,
} from "@/lib/documents";

function signInAgain() {
  const next = encodeURIComponent(
    window.location.pathname + window.location.search,
  );
  // The session ended mid-form; resume here after signing in.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${next}`);
}

export function UploadDocumentForm({
  workspaceId,
  buttonRef,
}: {
  workspaceId: string;
  buttonRef?: RefObject<HTMLButtonElement | null>;
}) {
  const router = useRouter();
  const internalRef = useRef<HTMLButtonElement>(null);
  const triggerRef = buttonRef ?? internalRef;
  const fileRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function upload(file: File) {
    setFailure(null);

    if (file.size === 0) {
      setFailure("Choose a .txt, .md, or .pdf file to upload.");
      return;
    }
    if (!isSupportedDocument(file.name)) {
      setFailure("Use a .txt, .md, or .pdf file.");
      return;
    }
    if (file.size > MAX_DOCUMENT_BYTES) {
      setFailure(`That file is ${formatBytes(file.size)}. The limit is 5 MB.`);
      return;
    }

    setPending(true);
    try {
      // Send the file as multipart; the browser sets the boundary.
      const data = new FormData();
      data.set("file", file);

      const response = await fetch(`/api/workspaces/${workspaceId}/documents`, {
        method: "POST",
        body: data,
      });

      if (response.status === 401) {
        signInAgain();
        return;
      }

      if (response.ok) {
        if (fileRef.current) fileRef.current.value = "";
        // Re-fetch the server page without a full navigation so the new
        // document (and the chat gate) update immediately.
        router.refresh();
        return;
      }

      const body = await response.json().catch(() => null);
      setFailure(
        response.status === 404
          ? "This workspace is no longer available."
          : documentFailure(
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

  function pick(file: File | null | undefined) {
    if (file) void upload(file);
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragging(false);
    pick(event.dataTransfer.files?.[0]);
  }

  return (
    <div>
      <input
        ref={fileRef}
        type="file"
        hidden
        accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          pick(file);
        }}
      />

      <button
        ref={triggerRef}
        type="button"
        disabled={pending}
        aria-busy={pending}
        onClick={() => fileRef.current?.click()}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={[
          "flex w-full items-center gap-2 rounded-lg border border-dashed px-2.5 py-2 text-left transition-colors duration-150 disabled:cursor-wait disabled:opacity-70",
          dragging
            ? "border-accent bg-accent/5"
            : "border-control hover:border-foreground/50 hover:bg-surface",
        ].join(" ")}
      >
        <span
          aria-hidden="true"
          className="grid size-7 shrink-0 place-items-center rounded-md border border-border bg-elevated text-muted"
        >
          <UploadIcon className="size-3.5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-foreground">
            {pending ? "Uploading…" : "Upload document"}
          </span>
          <span className="mt-0.5 block truncate text-xs text-muted">
            .txt, .md, or .pdf, up to 5 MB
          </span>
        </span>
      </button>

      {failure ? (
        <p role="alert" className="mt-2 px-1 text-xs leading-5 text-danger">
          {failure}
        </p>
      ) : null}
    </div>
  );
}
