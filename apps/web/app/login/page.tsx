import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { AuthShell } from "@/components/auth-shell";
import { getMe } from "@/lib/api";
import { safeNextPath } from "@/lib/next-path";
import { getSessionToken } from "@/lib/session";

export const metadata = { title: "Sign in — Ragnest" };

// Reads the session cookie, so it cannot be prerendered.
export const instant = false;

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const params = await searchParams;
  const next = safeNextPath(
    typeof params.next === "string" ? params.next : null,
  );

  const token = await getSessionToken();
  if (token) {
    // A cookie is not proof of a live session: the token may have expired or
    // been rejected. Only bounce when the API accepts it, or / and /login
    // would redirect to each other forever.
    const user = await getMe(token).catch(() => null);
    if (user) redirect(next ?? "/");
  }

  return (
    <AuthShell
      title="Welcome back."
      intro="Sign in to get back to your workspaces and the documents in them."
      footer={
        <p className="text-[15px] text-muted">
          New to Ragnest?{" "}
          <Link
            href={
              next ? `/signup?next=${encodeURIComponent(next)}` : "/signup"
            }
            className="text-action underline-offset-4 hover:underline"
          >
            Create an account
          </Link>
        </p>
      }
    >
      <AuthForm mode="login" nextPath={next ?? undefined} />
    </AuthShell>
  );
}
