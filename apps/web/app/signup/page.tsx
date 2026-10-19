import Link from "next/link";
import { AuthForm } from "@/components/auth-form";
import { AuthShell } from "@/components/auth-shell";

export const metadata = { title: "Create an account — Ragnest" };

export default function SignupPage() {
  return (
    <AuthShell
      title="Start asking your documents."
      intro="Create an account, then upload what you want to search. Every answer comes back with the file and page it came from."
      footer={
        <p className="text-[15px] text-muted">
          Already have an account?{" "}
          <Link href="/login" className="text-action underline-offset-4 hover:underline">
            Sign in
          </Link>
        </p>
      }
    >
      <AuthForm mode="signup" />
    </AuthShell>
  );
}
