import Link from "next/link";
import { redirect } from "next/navigation";
import { SignOut } from "@/components/sign-out";
import { ApiError, getMe } from "@/lib/api";
import { parseApiDate } from "@/lib/dates";
import { getSessionToken } from "@/lib/session";
import { tokenExpiry } from "@/lib/token";

export const metadata = { title: "Your account — Ragnest" };

// Reads the session cookie and calls the API, so it cannot be prerendered.
export const instant = false;

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZoneName: "short",
});

export default async function AccountPage() {
  const token = await getSessionToken();
  if (!token) redirect("/login");

  let user;
  try {
    user = await getMe(token);
  } catch (error) {
    // An expired or rejected token is a normal end of session, not a failure.
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    throw error;
  }

  const expires = tokenExpiry(token);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-6 pt-24 pb-20">
      <p className="text-sm font-semibold tracking-tight text-foreground">
        Ragnest
      </p>

      <h1 className="mt-10 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
        You&apos;re signed in.
      </h1>

      <p className="mt-4 max-w-prose text-base leading-7 text-muted">
        The API recognised your token. This is the account it belongs to.
      </p>

      <dl className="mt-10 divide-y divide-border border-y border-border">
        <div className="py-4">
          <dt className="text-sm text-muted">Email</dt>
          <dd className="mt-1 text-base">{user.email}</dd>
        </div>
        <div className="py-4">
          <dt className="text-sm text-muted">Account ID</dt>
          <dd className="mt-1 font-mono text-sm break-all">{user.id}</dd>
        </div>
        <div className="py-4">
          <dt className="text-sm text-muted">Member since</dt>
          <dd className="mt-1 text-base">
            {dateFormat.format(parseApiDate(user.created_at))}
          </dd>
        </div>
        {expires ? (
          <div className="py-4">
            <dt className="text-sm text-muted">Signed in until</dt>
            <dd className="mt-1 text-base">{dateFormat.format(expires)}</dd>
          </div>
        ) : null}
      </dl>

      <div className="mt-10 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <SignOut />
        <Link
          href="/"
          className="text-sm text-accent underline-offset-4 transition-colors duration-150 hover:underline"
        >
          Back to your workspaces
        </Link>
      </div>
    </main>
  );
}
