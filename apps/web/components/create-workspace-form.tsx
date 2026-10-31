"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/button";
import { Field } from "@/components/field";

type Failure = { detail: string; fields?: { field: string; message: string }[] };

/**
 * The create card and its form. Collapsed it is the one prominent action on
 * the picker; opened it reveals the same form (and the same submit logic) in
 * place.
 */
export function CreateWorkspaceForm() {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function close() {
    setOpen(false);
    setFailure(null);
    setFieldErrors({});
  }

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

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group flex w-full items-center justify-center gap-3 rounded-xl border border-border bg-surface px-6 py-5 text-sm font-medium text-foreground transition-colors duration-150 hover:border-control hover:bg-elevated"
      >
        <span
          aria-hidden="true"
          className="grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-elevated text-muted transition-colors duration-150 group-hover:border-control group-hover:text-foreground"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path
              d="M7 2.5v9M2.5 7h9"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </span>
        Create a new workspace
      </button>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="rounded-xl border border-border bg-surface p-5"
    >
      <Field
        label="Workspace name"
        name="name"
        required
        placeholder="Acme"
        autoComplete="off"
        error={fieldErrors.name}
        autoFocus
      />

      {failure ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {failure.detail}
        </p>
      ) : null}

      <div className="mt-5 flex items-center gap-4">
        <Button type="submit" pending={pending}>
          Create workspace
        </Button>
        <button
          type="button"
          onClick={close}
          className="text-sm text-muted transition-colors duration-150 hover:text-foreground"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
