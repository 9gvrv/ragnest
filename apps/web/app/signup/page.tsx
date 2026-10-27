import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { AuthShell } from "@/components/auth-shell";
import { getSessionToken } from "@/lib/session";

export const metadata = { title: "Create an account — Ragnest" };

// Reads the session cookie, so it cannot be prerendered.
export const instant = false;

export default async function SignupPage({
  searchParams,
}: PageProps<"/signup">) {
  const params = await searchParams;
  const next = typeof params.next === "string" ? params.next : undefined;
  const safeNext = next?.startsWith("/") && !next.startsWith("//") ? next : null;

  if (await getSessionToken()) redirect(safeNext ?? "/");

  return (
    <AuthShell
      title="Start asking your documents."
      intro="Create an account, then upload what you want to search. Every answer comes back with the file and page it came from."
      footer={
        <p className="text-[15px] text-muted">
          Already have an account?{" "}
          <Link
            href={
              next ? `/login?next=${encodeURIComponent(next)}` : "/login"
            }
            className="text-action underline-offset-4 hover:underline"
          >
            Sign in
          </Link>
        </p>
      }
    >
      <AuthForm mode="signup" nextPath={next} />
    </AuthShell>
  );
}
