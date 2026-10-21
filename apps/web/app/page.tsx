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
    <main className="mx-auto flex w-full max-w-136 flex-1 flex-col px-6 pt-[14vh] pb-20">
      <p className="text-[13px] font-medium tracking-[0.08em] text-action">
        Ragnest
      </p>

      <h1 className="mt-6 font-serif text-[clamp(2.25rem,5vw,3rem)] leading-[1.1] tracking-[-0.02em]">
        You&apos;re signed in.
      </h1>

      <p className="mt-5 max-w-[60ch] font-serif text-[17px] leading-[1.65] text-muted">
        The API recognised your token. This is the account it belongs to.
      </p>

      <dl className="mt-10 divide-y divide-rule border-y border-rule">
        <div className="py-4">
          <dt className="text-[13px] text-muted">Email</dt>
          <dd className="mt-1 text-[15px]">{user.email}</dd>
        </div>
        <div className="py-4">
          <dt className="text-[13px] text-muted">Account ID</dt>
          <dd className="mt-1 font-mono text-[13px] break-all">{user.id}</dd>
        </div>
        <div className="py-4">
          <dt className="text-[13px] text-muted">Member since</dt>
          <dd className="mt-1 text-[15px]">
            {dateFormat.format(parseApiDate(user.created_at))}
          </dd>
        </div>
        {expires ? (
          <div className="py-4">
            <dt className="text-[13px] text-muted">Signed in until</dt>
            <dd className="mt-1 text-[15px]">{dateFormat.format(expires)}</dd>
          </div>
        ) : null}
      </dl>

      <div className="mt-10 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <SignOut />
        <p className="text-[13px] text-muted">
          Workspaces arrive in the next milestone.
        </p>
      </div>
    </main>
  );
}
