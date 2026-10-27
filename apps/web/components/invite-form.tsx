"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/button";
import { Field } from "@/components/field";

type Failure = { detail: string; fields?: { field: string; message: string }[] };

type Created = { email: string; role: string; link: string };

function signInAgain() {
  const next = encodeURIComponent(window.location.pathname);
  // The session ended mid-form; resume here after signing in.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${next}`);
}

export function InviteForm({ workspaceId }: { workspaceId: string }) {
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [hint, setHint] = useState<string | null>(null);
  const [created, setCreated] = useState<Created | null>(null);
  const [copied, setCopied] = useState(false);

  async function readFailure(response: Response) {
    const body: Failure = await response.json().catch(() => ({
      detail: "Something went wrong. Try again.",
    }));
    if (body.fields?.length) {
      setFieldErrors(
        Object.fromEntries(body.fields.map((f) => [f.field, f.message])),
      );
      return;
    }
    setFailure(body.detail);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setPending(true);
    setFailure(null);
    setFieldErrors({});
    setCreated(null);
    setCopied(false);

    const data = new FormData(form);
    const email = String(data.get("email") ?? "");
    const role = data.get("role") === "admin" ? "admin" : "member";

    try {
      // First ask whether that address already has an account, so the form can
      // say whether the person still needs to sign up.
      const checkResponse = await fetch(
        `/api/workspaces/${workspaceId}/invitations/check`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        },
      );

      if (checkResponse.status === 401) {
        signInAgain();
        return;
      }
      if (!checkResponse.ok) {
        await readFailure(checkResponse);
        return;
      }

      const check: { exists: boolean } = await checkResponse.json();
      setHint(
        check.exists
          ? null
          : "No Ragnest account yet — they'll need to sign up with this email.",
      );

      const response = await fetch(
        `/api/workspaces/${workspaceId}/invitations`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, role }),
        },
      );

      if (response.status === 401) {
        signInAgain();
        return;
      }
      if (!response.ok) {
        await readFailure(response);
        return;
      }

      const body = await response.json();
      form.reset();
      if (typeof body.token === "string" && body.token) {
        // The API's own `link` is internal plumbing; the shareable address is
        // this web route.
        setCreated({
          email: String(body.email),
          role: String(body.role),
          link: `${window.location.origin}/invite/${body.token}`,
        });
      }
    } catch {
      setFailure("Can't reach the server. Try again.");
    } finally {
      setPending(false);
    }
  }

  async function copyLink() {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setFailure("Couldn't copy the link. Select it and copy it yourself.");
    }
  }

  return (
    <div>
      <form onSubmit={onSubmit} noValidate className="max-w-[40ch] space-y-5">
        <Field
          label="Email"
          name="email"
          type="email"
          required
          autoComplete="off"
          placeholder="teammate@example.com"
          error={fieldErrors.email}
        />

        {hint ? <p className="text-[13px] text-muted">{hint}</p> : null}

        <div>
          <label htmlFor="invite-role" className="block text-[13px] font-medium">
            Role
          </label>
          <select
            id="invite-role"
            name="role"
            defaultValue="member"
            className="mt-2 w-full border-0 border-b border-control bg-transparent py-2 text-[15px] focus:border-action"
          >
            <option value="member">member — can search the documents</option>
            <option value="admin">
              admin — can also invite and remove members
            </option>
          </select>
        </div>

        {failure ? (
          <p role="alert" className="text-[13px] text-danger">
            {failure}
          </p>
        ) : null}

        <Button type="submit" pending={pending}>
          Create invite link
        </Button>
      </form>

      {created ? (
        <div className="mt-6 border border-rule p-4">
          <p className="text-[13px] text-muted">
            Share this link with {created.email}. They can sign in or create an
            account with that address, then join as {created.role}.
          </p>
          <div className="mt-3 flex items-start gap-3">
            <code className="min-w-0 flex-1 font-mono text-[13px] break-all">
              {created.link}
            </code>
            <button
              type="button"
              onClick={copyLink}
              className="shrink-0 rounded-[3px] border border-rule px-3 py-1.5 text-[13px] text-action transition-colors hover:border-action"
            >
              {copied ? "Copied" : "Copy link"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
