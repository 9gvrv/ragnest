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
    <main className="mx-auto flex w-full max-w-136 flex-1 flex-col px-6 pt-[14vh] pb-20">
      <header>
        <p className="text-[13px] font-medium tracking-[0.08em] text-action">
          Ragnest
        </p>
        <h1 className="mt-6 font-serif text-[clamp(2.25rem,5vw,3rem)] leading-[1.1] tracking-[-0.02em]">
          Your workspaces.
        </h1>
        <p className="mt-5 max-w-[60ch] font-serif text-[17px] leading-[1.65] text-muted">
          Each workspace holds its own documents. Start one, then invite the
          people who should be able to search it.
        </p>
      </header>

      {pending.length > 0 ? (
        <Link
          href="/invitations"
          className="group mt-10 flex items-baseline gap-3 border-y border-rule py-4 text-[15px] transition-colors hover:text-action"
        >
          <span aria-hidden className="size-2 shrink-0 bg-saffron" />
          <span>
            You have {pending.length} pending invitation
            {pending.length === 1 ? "" : "s"}.
          </span>
          <span className="ml-auto shrink-0 text-action underline-offset-4 group-hover:underline">
            Review
          </span>
        </Link>
      ) : null}

      <section aria-labelledby="workspaces-heading" className="mt-12">
        <div className="flex items-baseline justify-between border-b border-rule pb-2">
          <h2
            id="workspaces-heading"
            className="text-[13px] font-medium tracking-[0.08em] text-muted"
          >
            Workspaces
          </h2>
          <span className="text-[13px] text-muted tabular-nums">
            {workspaces.length}
          </span>
        </div>

        {workspaces.length > 0 ? (
          <ul className="divide-y divide-rule">
            {workspaces.map((workspace) => (
              <li key={workspace.id}>
                <Link
                  href={`/workspaces/${workspace.id}`}
                  className="group flex items-baseline justify-between gap-6 py-5"
                >
                  <span className="font-serif text-[22px] leading-tight group-hover:text-action">
                    {workspace.name}
                  </span>
                  <span className="shrink-0 text-[13px] text-muted">
                    Since {dateFormat.format(parseApiDate(workspace.created_at))}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-8 font-serif text-[17px] leading-[1.65] text-muted">
            No workspaces yet. Create one to get started.
          </p>
        )}
      </section>

      <section aria-labelledby="create-heading" className="mt-12">
        <h2 id="create-heading" className="text-[13px] font-medium tracking-[0.08em] text-muted">
          New workspace
        </h2>
        <div className="mt-5">
          <CreateWorkspaceForm />
        </div>
      </section>

      <footer className="mt-16 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-t border-rule pt-6">
        <SignOut />
        <Link
          href="/account"
          className="text-[15px] text-action underline-offset-4 hover:underline"
        >
          Your account
        </Link>
      </footer>
    </main>
  );
}
