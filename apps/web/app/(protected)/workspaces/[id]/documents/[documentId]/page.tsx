import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { DeleteDocumentButton } from "@/components/delete-document-button";
import {
  ApiError,
  getDocument,
  getMe,
  getWorkspace,
  listMembers,
} from "@/lib/api";
import { parseApiDate } from "@/lib/dates";
import { canManageDocument, formatBytes, formatCount } from "@/lib/documents";
import { getSessionToken } from "@/lib/session";

// Reads the session cookie and calls the API, so it cannot be prerendered.
export const instant = false;

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

export async function generateMetadata({
  params,
}: PageProps<"/workspaces/[id]/documents/[documentId]">): Promise<Metadata> {
  const { id, documentId } = await params;
  const token = await getSessionToken();
  if (!token) return { title: "Document — Ragnest" };

  try {
    const document = await getDocument(token, id, documentId);
    return { title: `${document.filename} — Ragnest` };
  } catch {
    return { title: "Document — Ragnest" };
  }
}

export default async function DocumentPage({
  params,
}: PageProps<"/workspaces/[id]/documents/[documentId]">) {
  const { id, documentId } = await params;
  const token = await getSessionToken();
  if (!token) {
    redirect(
      `/login?next=${encodeURIComponent(`/workspaces/${id}/documents/${documentId}`)}`,
    );
  }

  let workspace;
  let document;
  let members;
  let me;
  try {
    [workspace, document, members, me] = await Promise.all([
      getWorkspace(token, id),
      getDocument(token, id, documentId),
      listMembers(token, id),
      getMe(token),
    ]);
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401) {
        redirect(
          `/login?next=${encodeURIComponent(`/workspaces/${id}/documents/${documentId}`)}`,
        );
      }
      if (error.status === 403) {
        return <NoAccess />;
      }
      if (error.status === 404 || error.status === 422) {
        notFound();
      }
    }
    throw error;
  }

  const myRole = members.find((member) => member.user_id === me.id)?.role;
  if (!myRole) return <NoAccess />;

  const canDelete = canManageDocument(myRole, me.id, document);
  const workspacePath = `/workspaces/${workspace.id}`;

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 pt-24 pb-20">
      <header>
        <Link
          href="/workspaces"
          className="text-sm font-semibold tracking-tight text-foreground underline-offset-4 transition-colors duration-150 hover:text-accent hover:underline"
        >
          Ragnest
        </Link>
        <Link
          href={workspacePath}
          className="mt-10 inline-flex items-center gap-1.5 text-sm text-muted transition-colors duration-150 hover:text-foreground"
        >
          <span aria-hidden>←</span>
          {workspace.name}
        </Link>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight break-all text-balance sm:text-5xl">
          {document.filename}
        </h1>
        <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
          <span>{document.content_type}</span>
          <span aria-hidden>·</span>
          <span className="tabular-nums">
            {formatBytes(document.size_bytes)}
          </span>
          {document.page_count !== null ? (
            <>
              <span aria-hidden>·</span>
              <span className="tabular-nums">
                {formatCount(document.page_count)} page
                {document.page_count === 1 ? "" : "s"}
              </span>
            </>
          ) : null}
          <span aria-hidden>·</span>
          <span className="tabular-nums">
            {formatCount(document.char_count)} characters
          </span>
        </p>
        <p className="mt-1 text-sm text-muted">
          Added {dateFormat.format(parseApiDate(document.created_at))}
        </p>
      </header>

      <section aria-labelledby="text-heading" className="mt-10">
        <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2">
          <h2
            id="text-heading"
            className="text-sm font-semibold text-foreground"
          >
            Extracted text
          </h2>
          {canDelete ? (
            <DeleteDocumentButton
              workspaceId={workspace.id}
              documentId={document.id}
              filename={document.filename}
              backHref={workspacePath}
              align="start"
            />
          ) : null}
        </div>

        <div className="mt-4 max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-surface p-5">
          <p className="text-sm leading-6 break-words whitespace-pre-wrap">
            {document.extracted_text}
          </p>
        </div>
      </section>
    </main>
  );
}

function NoAccess() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 pt-24 pb-20">
      <p className="text-sm font-semibold tracking-tight text-foreground">
        Ragnest
      </p>
      <h1 className="mt-10 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
        You&apos;re not a member of this workspace.
      </h1>
      <p className="mt-4 max-w-prose text-base leading-7 text-muted">
        Ask whoever invited you for a new link, or go back to the workspaces you
        do belong to.
      </p>
      <Link
        href="/workspaces"
        className="mt-8 text-sm text-accent underline-offset-4 transition-colors duration-150 hover:underline"
      >
        Back to your workspaces
      </Link>
    </main>
  );
}
