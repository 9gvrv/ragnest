import Link from "next/link";
import { redirect } from "next/navigation";
import { InvitationActions } from "@/components/invitation-actions";
import { ApiError, listPendingInvitations } from "@/lib/api";
import { parseApiDate } from "@/lib/dates";
import { getSessionToken } from "@/lib/session";

export const metadata = { title: "Invitations — Ragnest" };

// Reads the session cookie and calls the API, so it cannot be prerendered.
export const instant = false;

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

export default async function InvitationsPage() {
  const token = await getSessionToken();
  if (!token) redirect("/login?next=/invitations");

  let pending;
  try {
    pending = await listPendingInvitations(token);
  } catch (error) {
    // An expired or rejected token is a normal end of session, not a failure.
    if (error instanceof ApiError && error.status === 401) {
      redirect("/login?next=/invitations");
    }
    throw error;
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 pt-24 pb-20">
      <header>
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-foreground underline-offset-4 transition-colors duration-150 hover:text-accent hover:underline"
        >
          Ragnest
        </Link>
        <h1 className="mt-10 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Invitations.
        </h1>
        <p className="mt-4 max-w-prose text-base leading-7 text-muted">
          Workspaces you&apos;ve been asked to join. Accepting adds you to the
          member list; declining leaves the invite dead.
        </p>
      </header>

      {pending.length > 0 ? (
        <ul className="mt-12 divide-y divide-border border-y border-border">
          {pending.map((invitation) => (
            <li
              key={invitation.invitation_id}
              className="flex flex-col gap-4 py-5 sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="min-w-0">
                <p className="text-base font-medium">
                  {invitation.workspace_name}
                </p>
                <p className="mt-1 text-sm text-muted">
                  Invited by {invitation.inviter_email ?? "someone"}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                  <span className="inline-flex items-center rounded-md border border-border bg-foreground/5 px-2 py-0.5 font-mono text-xs leading-normal">
                    {invitation.role}
                  </span>
                  <span>
                    Expires{" "}
                    {dateFormat.format(parseApiDate(invitation.expires_at))}
                  </span>
                </div>
              </div>
              <InvitationActions token={invitation.token} />
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-12 rounded-lg border border-border bg-surface px-5 py-6">
          <p className="text-sm text-muted">No pending invitations.</p>
          <Link
            href="/"
            className="mt-3 inline-block text-sm text-accent underline-offset-4 transition-colors duration-150 hover:underline"
          >
            Back to your workspaces
          </Link>
        </div>
      )}
    </main>
  );
}
