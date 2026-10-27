import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { DeleteWorkspaceButton } from "@/components/delete-workspace-button";
import { InviteForm } from "@/components/invite-form";
import { RemoveMemberButton } from "@/components/remove-member-button";
import {
  ApiError,
  getMe,
  getWorkspace,
  listMembers,
  type ApiMember,
  type ApiRole,
} from "@/lib/api";
import { parseApiDate } from "@/lib/dates";
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
    <span className="inline-block rounded-[3px] border border-rule px-1.5 py-0.5 text-[12px] leading-normal text-muted">
      {role}
    </span>
  );
}

export default async function WorkspacePage({
  params,
}: PageProps<"/workspaces/[id]">) {
  const { id } = await params;
  const token = await getSessionToken();
  if (!token) {
    redirect(`/login?next=${encodeURIComponent(`/workspaces/${id}`)}`);
  }

  let workspace;
  let members;
  let me;
  try {
    [workspace, members, me] = await Promise.all([
      getWorkspace(token, id),
      listMembers(token, id),
      getMe(token),
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
          {workspace.name}
        </h1>
        <p className="mt-3 text-[13px] text-muted">
          Created {dateFormat.format(parseApiDate(workspace.created_at))}
        </p>
      </header>

      <section aria-labelledby="members-heading" className="mt-12">
        <div className="flex items-baseline justify-between border-b border-rule pb-2">
          <h2
            id="members-heading"
            className="text-[13px] font-medium tracking-[0.08em] text-muted"
          >
            Members
          </h2>
          <span className="text-[13px] text-muted tabular-nums">
            {members.length}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-rule text-[13px] text-muted">
                <th scope="col" className="py-2 font-normal">
                  Member
                </th>
                <th scope="col" className="py-2 font-normal">
                  Role
                </th>
                <th scope="col" className="py-2 font-normal">
                  Joined
                </th>
                {hasRemovableMember ? (
                  <th scope="col" className="py-2 text-right font-normal">
                    <span className="sr-only">Actions</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {members.map((member) => (
                <tr key={member.user_id}>
                  <td className="py-4 pr-4 text-[15px] break-all">
                    {member.email}
                    {member.user_id === me.id ? (
                      <span className="ml-2 text-[13px] text-muted">you</span>
                    ) : null}
                  </td>
                  <td className="py-4 pr-4">
                    <RoleTag role={member.role} />
                  </td>
                  <td className="py-4 pr-4 text-[13px] whitespace-nowrap text-muted">
                    {dateFormat.format(parseApiDate(member.joined_at))}
                  </td>
                  {hasRemovableMember ? (
                    <td className="py-4 text-right">
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
            className="text-[13px] font-medium tracking-[0.08em] text-muted"
          >
            Invite someone
          </h2>
          <p className="mt-3 max-w-[55ch] font-serif text-[17px] leading-[1.65] text-muted">
            Ragnest doesn&apos;t send email yet. Create a link and send it
            yourself.
          </p>
          <div className="mt-5">
            <InviteForm workspaceId={workspace.id} />
          </div>
        </section>
      ) : null}

      {myRole === "creator" ? (
        <section
          aria-labelledby="delete-heading"
          className="mt-16 border-t border-rule pt-8"
        >
          <h2
            id="delete-heading"
            className="text-[13px] font-medium tracking-[0.08em] text-muted"
          >
            Delete this workspace
          </h2>
          <p className="mt-3 max-w-[55ch] font-serif text-[17px] leading-[1.65] text-muted">
            Everything inside goes with it, for every member. This can&apos;t be
            undone.
          </p>
          <div className="mt-5">
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
    <main className="mx-auto flex w-full max-w-136 flex-1 flex-col px-6 pt-[14vh] pb-20">
      <p className="text-[13px] font-medium tracking-[0.08em] text-action">
        Ragnest
      </p>
      <h1 className="mt-6 font-serif text-[clamp(2.25rem,5vw,3rem)] leading-[1.1] tracking-[-0.02em]">
        You&apos;re not a member of this workspace.
      </h1>
      <p className="mt-5 max-w-[60ch] font-serif text-[17px] leading-[1.65] text-muted">
        Ask whoever invited you for a new link, or go back to the workspaces you
        do belong to.
      </p>
      <Link
        href="/"
        className="mt-8 text-[15px] text-action underline-offset-4 hover:underline"
      >
        Back to your workspaces
      </Link>
    </main>
  );
}
