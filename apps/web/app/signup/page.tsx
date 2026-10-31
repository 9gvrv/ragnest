import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { AuthShell } from "@/components/auth-shell";
import { getMe } from "@/lib/api";
import { safeNextPath } from "@/lib/next-path";
import { getSessionToken } from "@/lib/session";

export const metadata = { title: "Create an account — Ragnest" };

// Reads the session cookie, so it cannot be prerendered.
export const instant = false;

export default async function SignupPage({
  searchParams,
}: PageProps<"/signup">) {
  const params = await searchParams;
  const next = safeNextPath(
    typeof params.next === "string" ? params.next : null,
  );

  const token = await getSessionToken();
  if (token) {
    // A cookie is not proof of a live session: see the login page.
    const user = await getMe(token).catch(() => null);
    if (user) redirect(next ?? "/");
  }

  return (
    <AuthShell
      title="Start asking your documents."
      intro="Create an account, then upload what you want to search. Every answer comes back with the file and page it came from."
      footer={
        <p className="text-sm text-muted">
          Already have an account?{" "}
          <Link
            href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"}
            className="text-accent underline-offset-4 transition-colors duration-150 hover:underline"
          >
            Sign in
          </Link>
        </p>
      }
    >
      <AuthForm mode="signup" nextPath={next ?? undefined} />
    </AuthShell>
  );
}
