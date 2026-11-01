import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import {
  ApiError,
  getMe,
  getWorkspace,
  listDocuments,
  listMembers,
} from "@/lib/api";
import { parseApiDate } from "@/lib/dates";
import type { WorkspaceChat } from "@/lib/chats";
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
  let allDocuments;
  try {
    [workspace, members, me, allDocuments] = await Promise.all([
      getWorkspace(token, id),
      listMembers(token, id),
      getMe(token),
      // Fetch the whole set: the All/Mine filter is applied here, and the chat
      // gate must know whether *any* document exists, not just the visible ones.
      listDocuments(token, id),
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

  const documents = mine
    ? allDocuments.filter((document) => document.uploaded_by === me.id)
    : allDocuments;

  // No chat backend yet. Typed placeholders keep the list easy to wire up.
  const chats: WorkspaceChat[] = [];

  return (
    <WorkspaceShell
      workspace={workspace}
      me={me}
      myRole={myRole}
      allDocuments={allDocuments}
      documents={documents}
      mine={mine}
      members={members}
      chats={chats}
    >
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 pt-16 pb-20">
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
      </main>
    </WorkspaceShell>
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
