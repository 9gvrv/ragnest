"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/button";
import { Field } from "@/components/field";

type Failure = { detail: string; fields?: { field: string; message: string }[] };

export function CreateWorkspaceForm() {
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setFailure(null);
    setFieldErrors({});

    const data = new FormData(event.currentTarget);
    const name = String(data.get("name") ?? "");

    try {
      const response = await fetch("/api/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });

      if (response.status === 401) {
        const next = encodeURIComponent(window.location.pathname);
        // Full navigation: the session cookie is gone, so cached payloads
        // must not be reused.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/login?next=${next}`);
        return;
      }

      if (response.ok) {
        const workspace: { id: string } = await response.json();
        // A full navigation drops prefetched payloads built before this
        // workspace existed.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(`/workspaces/${workspace.id}`);
        return;
      }

      const body: Failure = await response.json().catch(() => ({
        detail: "Something went wrong. Try again.",
      }));

      if (body.fields?.length) {
        setFieldErrors(
          Object.fromEntries(body.fields.map((f) => [f.field, f.message])),
        );
      } else {
        setFailure({ detail: body.detail });
      }
    } catch {
      setFailure({ detail: "Can't reach the server. Try again." });
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-sm space-y-5">
      <Field
        label="Workspace name"
        name="name"
        required
        placeholder="Acme"
        autoComplete="off"
        error={fieldErrors.name}
      />

      {failure ? (
        <p role="alert" className="text-sm text-danger">
          {failure.detail}
        </p>
      ) : null}

      <Button type="submit" pending={pending}>
        Create workspace
      </Button>
    </form>
  );
}
