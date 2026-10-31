import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { DeleteDocumentButton } from "@/components/delete-document-button";
import { DeleteWorkspaceButton } from "@/components/delete-workspace-button";
import { InviteForm } from "@/components/invite-form";
import { RemoveMemberButton } from "@/components/remove-member-button";
import { UploadDocumentForm } from "@/components/upload-document-form";
import {
  ApiError,
  getMe,
  getWorkspace,
  listDocuments,
  listMembers,
  type ApiDocument,
  type ApiMember,
  type ApiRole,
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
}: PageProps<"/workspaces/[id]">): Promise<Metadata> {
  const { id } = await params;
  const token = await getSessionToken();
  if (!token) return { title: "Workspace — Ragnest" };

  try {
    const workspace = await getWorkspace(token, id);
    return { title: `${workspace.name} — Ragnest` };
  } catch {
    return { title: "Workspace — Ragnest" };
  }
}

function RoleTag({ role }: { role: ApiRole }) {
  return (
    <span className="inline-flex items-center rounded-md border border-border bg-foreground/5 px-2 py-0.5 font-mono text-xs leading-normal text-muted">
      {role}
    </span>
  );
}

export default async function WorkspacePage({
  params,
  searchParams,
}: PageProps<"/workspaces/[id]">) {
  const { id } = await params;
  const query = await searchParams;
  const mine = query.mine === "true";
  const token = await getSessionToken();
  if (!token) {
    redirect(`/login?next=${encodeURIComponent(`/workspaces/${id}`)}`);
  }

  let workspace;
  let members;
  let me;
  let documents;
  try {
    [workspace, members, me, documents] = await Promise.all([
      getWorkspace(token, id),
      listMembers(token, id),
      getMe(token),
      listDocuments(token, id, mine),
    ]);
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401) {
        redirect(`/login?next=${encodeURIComponent(`/workspaces/${id}`)}`);
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

  const canInvite = myRole === "creator" || myRole === "admin";
  const canRemove = (member: ApiMember) => {
    if (member.user_id === me.id) return false; // never yourself
    if (member.role === "creator") return false; // never the creator
    if (myRole === "creator") return true;
    if (myRole === "admin") return member.role === "member";
    return false; // plain members manage nobody
  };
  const hasRemovableMember = members.some(canRemove);

  const canDeleteDocument = (document: ApiDocument) =>
    canManageDocument(myRole, me.id, document);
  const hasDeletableDocument = documents.some(canDeleteDocument);
  const hasPageCounts = documents.some(
    (document) => document.page_count !== null,
  );

  const documentsPath = `/workspaces/${workspace.id}`;
  const filterClass = (active: boolean) =>
    active
      ? "text-foreground"
      : "text-muted transition-colors duration-150 hover:text-foreground";

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 pt-24 pb-20">
      <header>
        <Link
          href="/workspaces"
          className="text-sm font-semibold tracking-tight text-foreground underline-offset-4 transition-colors duration-150 hover:text-accent hover:underline"
        >
          Ragnest
        </Link>
        <h1 className="mt-10 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          {workspace.name}
        </h1>
        <p className="mt-3 text-sm text-muted">
          Created {dateFormat.format(parseApiDate(workspace.created_at))}
        </p>
      </header>

      <section aria-labelledby="documents-heading" className="mt-12">
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <h2
            id="documents-heading"
            className="text-sm font-semibold text-foreground"
          >
            Documents
          </h2>
          <span className="font-mono text-xs text-muted tabular-nums">
            {documents.length}
          </span>
        </div>

        <nav
          aria-label="Filter documents"
          className="mt-3 flex items-center gap-4 text-sm"
        >
          <Link
            href={documentsPath}
            aria-current={mine ? undefined : "page"}
            className={filterClass(!mine)}
          >
            All
          </Link>
          <Link
            href={`${documentsPath}?mine=true`}
            aria-current={mine ? "page" : undefined}
            className={filterClass(mine)}
          >
            Mine
          </Link>
        </nav>

        <UploadDocumentForm workspaceId={workspace.id} />

        {documents.length === 0 ? (
          <p className="mt-6 text-sm text-muted">
            {mine
              ? "You haven't uploaded any documents in this workspace yet."
              : "No documents yet. Upload one to get started."}
          </p>
        ) : (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border text-xs text-muted">
                  <th scope="col" className="py-2 font-medium">
                    Document
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    Size
                  </th>
                  {hasPageCounts ? (
                    <th scope="col" className="py-2 font-medium">
                      Pages
                    </th>
                  ) : null}
                  <th scope="col" className="py-2 font-medium">
                    Characters
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    Added
                  </th>
                  {hasDeletableDocument ? (
                    <th scope="col" className="py-2 text-right font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {documents.map((document) => (
                  <tr key={document.id}>
                    <td className="py-3 pr-4 text-sm">
                      <Link
                        href={`${documentsPath}/documents/${document.id}`}
                        className="font-medium break-all text-foreground underline-offset-4 transition-colors duration-150 hover:text-accent hover:underline"
                      >
                        {document.filename}
                      </Link>
                      <span className="mt-0.5 block text-xs text-muted">
                        {document.content_type}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-sm whitespace-nowrap text-muted tabular-nums">
                      {formatBytes(document.size_bytes)}
                    </td>
                    {hasPageCounts ? (
                      <td className="py-3 pr-4 text-sm whitespace-nowrap text-muted tabular-nums">
                        {document.page_count !== null
                          ? formatCount(document.page_count)
                          : null}
                      </td>
                    ) : null}
                    <td className="py-3 pr-4 text-sm whitespace-nowrap text-muted tabular-nums">
                      {formatCount(document.char_count)}
                    </td>
                    <td className="py-3 pr-4 text-sm whitespace-nowrap text-muted">
                      {dateFormat.format(parseApiDate(document.created_at))}
                    </td>
                    {hasDeletableDocument ? (
                      <td className="py-3 text-right">
                        {canDeleteDocument(document) ? (
                          <DeleteDocumentButton
                            workspaceId={workspace.id}
                            documentId={document.id}
                            filename={document.filename}
                          />
                        ) : null}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="members-heading" className="mt-12">
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <h2
            id="members-heading"
            className="text-sm font-semibold text-foreground"
          >
            Members
          </h2>
          <span className="font-mono text-xs text-muted tabular-nums">
            {members.length}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border text-xs text-muted">
                <th scope="col" className="py-2 font-medium">
                  Member
                </th>
                <th scope="col" className="py-2 font-medium">
                  Role
                </th>
                <th scope="col" className="py-2 font-medium">
                  Joined
                </th>
                {hasRemovableMember ? (
                  <th scope="col" className="py-2 text-right font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {members.map((member) => (
                <tr key={member.user_id}>
                  <td className="py-3 pr-4 text-sm break-all">
                    {member.email}
                    {member.user_id === me.id ? (
                      <span className="ml-2 text-xs text-muted">you</span>
                    ) : null}
                  </td>
                  <td className="py-3 pr-4">
                    <RoleTag role={member.role} />
                  </td>
                  <td className="py-3 pr-4 text-sm whitespace-nowrap text-muted">
                    {dateFormat.format(parseApiDate(member.joined_at))}
                  </td>
                  {hasRemovableMember ? (
                    <td className="py-3 text-right">
                      {canRemove(member) ? (
                        <RemoveMemberButton
                          workspaceId={workspace.id}
                          userId={member.user_id}
                          email={member.email}
                        />
                      ) : null}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {canInvite ? (
        <section aria-labelledby="invite-heading" className="mt-12">
          <h2
            id="invite-heading"
            className="text-sm font-semibold text-foreground"
          >
            Invite someone
          </h2>
          <p className="mt-3 max-w-prose text-sm leading-6 text-muted">
            Ragnest doesn&apos;t send email yet. Create a link and send it
            yourself.
          </p>
          <div className="mt-4">
            <InviteForm workspaceId={workspace.id} />
          </div>
        </section>
      ) : null}

      {myRole === "creator" ? (
        <section
          aria-labelledby="delete-heading"
          className="mt-16 border-t border-border pt-8"
        >
          <h2
            id="delete-heading"
            className="text-sm font-semibold text-foreground"
          >
            Delete this workspace
          </h2>
          <p className="mt-3 max-w-prose text-sm leading-6 text-muted">
            Everything inside goes with it, for every member. This can&apos;t be
            undone.
          </p>
          <div className="mt-4">
            <DeleteWorkspaceButton
              workspaceId={workspace.id}
              workspaceName={workspace.name}
            />
          </div>
        </section>
      ) : null}
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
