import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { AuthShell } from "@/components/auth-shell";
import { getSessionToken } from "@/lib/session";

export const metadata = { title: "Sign in — Ragnest" };

// Reads the session cookie, so it cannot be prerendered.
export const instant = false;

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const params = await searchParams;
  const next = typeof params.next === "string" ? params.next : undefined;
  const safeNext = next?.startsWith("/") && !next.startsWith("//") ? next : null;

  if (await getSessionToken()) redirect(safeNext ?? "/");

  return (
    <AuthShell
      title="Welcome back."
      intro="Sign in to get back to your workspaces and the documents in them."
      footer={
        <p className="text-[15px] text-muted">
          New to Ragnest?{" "}
          <Link
            href={
              next
                ? `/signup?next=${encodeURIComponent(next)}`
                : "/signup"
            }
            className="text-action underline-offset-4 hover:underline"
          >
            Create an account
          </Link>
        </p>
      }
    >
      <AuthForm mode="login" nextPath={next} />
    </AuthShell>
  );
}
