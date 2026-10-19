import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { AuthShell } from "@/components/auth-shell";
import { getSessionToken } from "@/lib/session";

export const metadata = { title: "Sign in — Ragnest" };

// Reads the session cookie, so it cannot be prerendered.
export const instant = false;

export default async function LoginPage() {
  if (await getSessionToken()) redirect("/");

  return (
    <AuthShell
      title="Welcome back."
      intro="Sign in to get back to your workspaces and the documents in them."
      footer={
        <p className="text-[15px] text-muted">
          New to Ragnest?{" "}
          <Link href="/signup" className="text-action underline-offset-4 hover:underline">
            Create an account
          </Link>
        </p>
      }
    >
      <AuthForm mode="login" />
    </AuthShell>
  );
}
