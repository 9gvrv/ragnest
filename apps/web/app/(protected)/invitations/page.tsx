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
    <main className="mx-auto flex w-full max-w-136 flex-1 flex-col px-6 pt-[14vh] pb-20">
      <header>
        <Link
          href="/"
          className="text-[13px] font-medium tracking-[0.08em] text-action underline-offset-4 hover:underline"
        >
          Ragnest
        </Link>
        <h1 className="mt-6 font-serif text-[clamp(2.25rem,5vw,3rem)] leading-[1.1] tracking-[-0.02em]">
          Invitations.
        </h1>
        <p className="mt-5 max-w-[60ch] font-serif text-[17px] leading-[1.65] text-muted">
          Workspaces you&apos;ve been asked to join. Accepting adds you to the
          member list; declining leaves the invite dead.
        </p>
      </header>

      {pending.length > 0 ? (
        <ul className="mt-12 divide-y divide-rule border-y border-rule">
          {pending.map((invitation) => (
            <li
              key={invitation.invitation_id}
              className="flex flex-col gap-4 py-6 sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="min-w-0">
                <p className="font-serif text-[22px] leading-tight">
                  {invitation.workspace_name}
                </p>
                <p className="mt-1 text-[13px] text-muted">
                  Invited by {invitation.inviter_email ?? "someone"}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
                  <span className="inline-block rounded-[3px] border border-rule px-1.5 py-0.5 text-[12px] leading-normal">
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
        <div className="mt-12 border-y border-rule py-8">
          <p className="font-serif text-[17px] leading-[1.65] text-muted">
            No pending invitations.
          </p>
          <Link
            href="/"
            className="mt-4 inline-block text-[15px] text-action underline-offset-4 hover:underline"
          >
            Back to your workspaces
          </Link>
        </div>
      )}
    </main>
  );
}
