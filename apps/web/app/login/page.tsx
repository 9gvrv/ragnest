import Link from "next/link";
import { AuthForm } from "@/components/auth-form";
import { AuthShell } from "@/components/auth-shell";

export const metadata = { title: "Sign in — Ragnest" };

export default function LoginPage() {
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
