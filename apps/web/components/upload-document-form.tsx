"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/button";
import { Field } from "@/components/field";
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

export function UploadDocumentForm({ workspaceId }: { workspaceId: string }) {
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFailure(null);

    // Send the form's own FormData: the browser sets the multipart boundary.
    const data = new FormData(event.currentTarget);
    const file = data.get("file");

    if (!(file instanceof File) || file.size === 0) {
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
      const response = await fetch(
        `/api/workspaces/${workspaceId}/documents`,
        {
          method: "POST",
          body: data,
        },
      );

      if (response.status === 401) {
        signInAgain();
        return;
      }

      if (response.ok) {
        // Full navigation so the list is rendered from the API's new state.
        window.location.assign(
          window.location.pathname + window.location.search,
        );
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

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start"
    >
      <div className="min-w-0 flex-1">
        <Field
          label="Upload a document"
          name="file"
          type="file"
          accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
          required
          hint=".txt, .md, or .pdf, up to 5 MB. The extracted text is kept; the original file isn't."
          error={failure ?? undefined}
          onChange={() => setFailure(null)}
          className="mt-2 block w-full rounded-md border border-control bg-background px-3 py-2 text-sm text-foreground transition-colors duration-150 file:mr-3 file:rounded-md file:border-0 file:bg-elevated file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-foreground hover:border-foreground/60 focus:border-foreground aria-invalid:border-danger"
        />
      </div>
      <Button type="submit" pending={pending} className="sm:mt-8">
        Upload
      </Button>
    </form>
  );
}
