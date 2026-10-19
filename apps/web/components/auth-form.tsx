"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/button";
import { Field } from "@/components/field";

type Mode = "signup" | "login";

type Failure = { detail: string; fields?: { field: string; message: string }[] };

const copy = {
  signup: {
    submit: "Create account",
    endpoint: "/api/auth/signup",
    passwordHint: "At least 8 characters.",
  },
  login: {
    submit: "Sign in",
    endpoint: "/api/auth/login",
    passwordHint: undefined,
  },
} as const;

export function AuthForm({ mode }: { mode: Mode }) {
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const labels = copy[mode];

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setFailure(null);
    setFieldErrors({});

    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "");
    const password = String(data.get("password") ?? "");

    try {
      const response = await fetch(labels.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (response.ok) {
        // The cookie just changed, so any prefetched payload for "/" was built
        // for a signed-out visitor and would bounce straight back here. A full
        // navigation discards the client router cache.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign("/");
        return;
      }

      const body: Failure = await response.json().catch(() => ({
        detail: "Something went wrong. Try again.",
      }));

      if (body.fields?.length) {
        setFieldErrors(
          Object.fromEntries(body.fields.map((f) => [f.field, f.message])),
        );
      }

      // 409 is the one status where the API's message is worth replacing with
      // guidance: the person needs a way out, not a restatement.
      if (response.status === 409) {
        setFailure({
          detail: "That email already has an account. Sign in instead.",
        });
      } else if (response.status === 401) {
        setFailure({ detail: "Email or password isn't right." });
      } else if (!body.fields?.length) {
        setFailure({ detail: body.detail });
      }
    } catch {
      setFailure({ detail: "Can't reach the server. Try again." });
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      <Field
        label="Email"
        name="email"
        type="email"
        autoComplete="email"
        required
        placeholder="you@example.com"
        error={fieldErrors.email}
      />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete={mode === "signup" ? "new-password" : "current-password"}
        required
        hint={labels.passwordHint}
        error={fieldErrors.password}
      />

      {failure ? (
        <p role="alert" className="text-[13px] text-danger">
          {failure.detail}
        </p>
      ) : null}

      <Button type="submit" pending={pending}>
        {labels.submit}
      </Button>
    </form>
  );
}
