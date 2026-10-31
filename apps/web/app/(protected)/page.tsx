import Link from "next/link";
import { redirect } from "next/navigation";
import { CreateWorkspaceForm } from "@/components/create-workspace-form";
import { SignOut } from "@/components/sign-out";
import {
  ApiError,
  listPendingInvitations,
  listWorkspaces,
} from "@/lib/api";
import { parseApiDate } from "@/lib/dates";
import { getSessionToken } from "@/lib/session";

export const metadata = { title: "Workspaces — Ragnest" };

// Reads the session cookie and calls the API, so it cannot be prerendered.
export const instant = false;

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

export default async function WorkspacesPage() {
  const token = await getSessionToken();
  if (!token) redirect("/login");

  let workspaces;
  let pending;
  try {
    [workspaces, pending] = await Promise.all([
      listWorkspaces(token),
      listPendingInvitations(token),
    ]);
  } catch (error) {
    // An expired or rejected token is a normal end of session, not a failure.
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    throw error;
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 pt-24 pb-20">
      <header>
        <p className="text-sm font-semibold tracking-tight text-foreground">
          Ragnest
        </p>
        <h1 className="mt-10 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Your workspaces.
        </h1>
        <p className="mt-4 max-w-prose text-base leading-7 text-muted">
          Each workspace holds its own documents. Start one, then invite the
          people who should be able to search it.
        </p>
      </header>

      {pending.length > 0 ? (
        <Link
          href="/invitations"
          className="group mt-10 flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 text-sm transition-colors duration-150 hover:border-control"
        >
          <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-accent" />
          <span>
            You have {pending.length} pending invitation
            {pending.length === 1 ? "" : "s"}.
          </span>
          <span className="ml-auto shrink-0 text-accent group-hover:underline">
            Review
          </span>
        </Link>
      ) : null}

      <section aria-labelledby="workspaces-heading" className="mt-12">
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <h2
            id="workspaces-heading"
            className="text-sm font-semibold text-foreground"
          >
            Workspaces
          </h2>
          <span className="font-mono text-xs text-muted tabular-nums">
            {workspaces.length}
          </span>
        </div>

        {workspaces.length > 0 ? (
          <ul className="divide-y divide-border">
            {workspaces.map((workspace) => (
              <li key={workspace.id}>
                <Link
                  href={`/workspaces/${workspace.id}`}
                  className="group flex items-baseline justify-between gap-6 py-4"
                >
                  <span className="text-base font-medium transition-colors duration-150 group-hover:text-accent">
                    {workspace.name}
                  </span>
                  <span className="shrink-0 text-sm text-muted">
                    Since {dateFormat.format(parseApiDate(workspace.created_at))}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-8 text-sm text-muted">
            No workspaces yet. Create one to get started.
          </p>
        )}
      </section>

      <section aria-labelledby="create-heading" className="mt-12">
        <h2 id="create-heading" className="text-sm font-semibold text-foreground">
          New workspace
        </h2>
        <div className="mt-4">
          <CreateWorkspaceForm />
        </div>
      </section>

      <footer className="mt-16 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-t border-border pt-6">
        <SignOut />
        <Link
          href="/account"
          className="text-sm text-accent underline-offset-4 transition-colors duration-150 hover:underline"
        >
          Your account
        </Link>
      </footer>
    </main>
  );
}
