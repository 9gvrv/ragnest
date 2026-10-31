import type { ReactNode } from "react";
import Link from "next/link";
import { AcceptInvitationButton } from "@/components/accept-invitation-button";
import { ApiError, getInvitationPreview } from "@/lib/api";
import { parseApiDate } from "@/lib/dates";
import { getSessionToken } from "@/lib/session";

export const metadata = { title: "Invitation — Ragnest" };

// Reads the URL token, the session cookie and the API, so it cannot be
// prerendered.
export const instant = false;

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

export default async function InvitePage({
  params,
}: PageProps<"/invite/[token]">) {
  const { token } = await params;

  let preview;
  try {
    preview = await getInvitationPreview(token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <InvitationShell title="This invitation link isn't valid.">
          <p className="text-base leading-7 text-muted">
            Check the address, or ask whoever invited you to send a new link.
          </p>
        </InvitationShell>
      );
    }
    throw error;
  }

  const next = encodeURIComponent(`/invite/${token}`);

  if (preview.status === "expired") {
    return (
      <InvitationShell title="This invitation expired.">
        <p className="text-base leading-7 text-muted">
          It was good until{" "}
          {dateFormat.format(parseApiDate(preview.expires_at))}. Ask whoever
          invited you to send a new one.
        </p>
      </InvitationShell>
    );
  }

  if (preview.status === "accepted") {
    return (
      <InvitationShell title={`You're already a member of ${preview.workspace_name}.`}>
        <Link
          href={`/workspaces/${preview.workspace_id}`}
          className="text-sm text-accent underline-offset-4 transition-colors duration-150 hover:underline"
        >
          Open the workspace
        </Link>
      </InvitationShell>
    );
  }

  if (preview.status === "declined") {
    return (
      <InvitationShell title="This invitation was declined.">
        <p className="text-base leading-7 text-muted">
          Ask whoever invited you if you&apos;d like a fresh link.
        </p>
      </InvitationShell>
    );
  }

  const hasSession = Boolean(await getSessionToken());

  return (
    <InvitationShell title={`Join ${preview.workspace_name}.`}>
      <div className="border-y border-border py-4">
        <p className="text-sm">
          {preview.inviter_email ?? "Someone"} invited you to join as{" "}
          <span className="inline-flex items-center rounded-md border border-border bg-foreground/5 px-2 py-0.5 font-mono text-xs leading-normal text-muted">
            {preview.role}
          </span>
        </p>
        <p className="mt-2 text-xs text-muted">
          For {preview.email}. This link is good until{" "}
          {dateFormat.format(parseApiDate(preview.expires_at))}.
        </p>
      </div>

      <div className="mt-8">
        {hasSession ? (
          <AcceptInvitationButton token={token} email={preview.email} />
        ) : (
          <>
            <p className="text-base leading-7">
              Sign in to accept this invitation.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-3">
              <Link
                href={`/login?next=${next}`}
                className="inline-flex h-9 items-center justify-center rounded-md bg-foreground px-4 text-sm font-medium text-background transition-colors duration-150 hover:bg-foreground/90"
              >
                Sign in
              </Link>
              <Link
                href={`/signup?next=${next}`}
                className="text-sm text-accent underline-offset-4 transition-colors duration-150 hover:underline"
              >
                Create an account
              </Link>
            </div>
          </>
        )}
      </div>
    </InvitationShell>
  );
}

function InvitationShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 pt-24 pb-20">
      <p className="text-sm font-semibold tracking-tight text-foreground">
        Ragnest
      </p>
      <h1 className="mt-10 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
        {title}
      </h1>
      <div className="mt-6">{children}</div>
    </main>
  );
}
