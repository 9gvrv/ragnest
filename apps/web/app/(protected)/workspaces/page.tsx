import Link from "next/link";
import { redirect } from "next/navigation";
import { CreateWorkspaceForm } from "@/components/create-workspace-form";
import { LogoMark } from "@/components/logo";
import { SignOut } from "@/components/sign-out";
import { ApiError, listPendingInvitations, listWorkspaces } from "@/lib/api";
import { parseApiDate } from "@/lib/dates";
import { getSessionToken } from "@/lib/session";
import { site } from "@/lib/site";

export const metadata = { title: "Workspaces — Ragnest" };

// Reads the session cookie and calls the API, so it cannot be prerendered.
export const instant = false;

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

/** Two letters for two names, two characters for one: "Acme Corp" → "AC". */
function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

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
    <div className="dark-surface flex min-h-svh flex-1 flex-col">
      <main className="mx-auto flex w-full max-w-[760px] flex-1 flex-col px-6 pt-16 pb-10 sm:pt-20 lg:pt-0">
        <div className="flex flex-col lg:flex-1 lg:justify-center">
          <header className="flex flex-col items-center text-center">
            <p className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-foreground">
              <LogoMark />
              {site.name}
            </p>
            <h1 className="mt-8 text-3xl font-semibold tracking-[-0.03em] text-balance sm:text-4xl">
              Welcome back!
            </h1>
            <p className="mt-3 text-sm text-muted">
              Create a new workspace or choose from an existing one.
            </p>

            {pending.length > 0 ? (
              <Link
                href="/invitations"
                className="mt-6 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-1.5 text-xs text-muted transition-colors duration-150 hover:border-control hover:text-foreground"
              >
                <span aria-hidden className="size-1.5 rounded-full bg-accent" />
                {pending.length} pending invitation
                {pending.length === 1 ? "" : "s"}
                <span aria-hidden className="text-border">
                  /
                </span>
                <span className="text-accent">Review</span>
              </Link>
            ) : null}
          </header>

        <div className="mt-10">
          <CreateWorkspaceForm />
        </div>

        {workspaces.length > 0 ? (
          <>
            <p className="mt-8 flex items-center gap-4 text-xs text-muted">
              <span aria-hidden className="h-px flex-1 bg-border" />
              OR continue to existing workspaces
              <span aria-hidden className="h-px flex-1 bg-border" />
            </p>

            <section aria-labelledby="workspaces-heading" className="mt-8">
              <h2
                id="workspaces-heading"
                className="px-1 text-xs font-medium text-muted"
              >
                Your workspaces
              </h2>

              <ul className="mt-3 overflow-hidden rounded-xl border border-border">
                {workspaces.map((workspace) => (
                  <li
                    key={workspace.id}
                    className="border-b border-border last:border-b-0"
                  >
                    <Link
                      href={`/workspaces/${workspace.id}`}
                      className="group flex items-center gap-4 px-4 py-3.5 transition-colors duration-150 hover:bg-surface focus-visible:-outline-offset-2"
                    >
                      <span
                        aria-hidden
                        className="grid size-10 shrink-0 place-items-center rounded-lg border border-border bg-elevated text-xs font-semibold tracking-[0.02em] text-foreground"
                      >
                        {initials(workspace.name)}
                      </span>

                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-foreground">
                          {workspace.name}
                        </span>
                        <span className="mt-0.5 block text-xs text-muted">
                          Since{" "}
                          {dateFormat.format(
                            parseApiDate(workspace.created_at),
                          )}
                        </span>
                      </span>

                      <svg
                        aria-hidden="true"
                        viewBox="0 0 16 16"
                        fill="none"
                        className="size-4 shrink-0 text-muted transition-[color,transform] duration-150 group-hover:translate-x-0.5 group-hover:text-foreground"
                      >
                        <path
                          d="M3 8h10M9 4l4 4-4 4"
                          stroke="currentColor"
                          strokeWidth="1.4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          </>
        ) : (
          <p className="mt-6 text-center text-sm text-muted">
            No workspaces yet. Create your first one above.
          </p>
        )}

        </div>

        <footer className="mt-16 flex items-center justify-between gap-6 border-t border-border pt-6 text-sm text-muted">
          <SignOut />
          <Link
            href="/account"
            className="transition-colors duration-150 hover:text-foreground"
          >
            Your account
          </Link>
        </footer>
      </main>
    </div>
  );
}
