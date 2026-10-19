import { redirect } from "next/navigation";
import { getSessionToken } from "@/lib/session";

/**
 * Guards the signed-in-only route. Presence of the cookie is enough to let the
 * page render: the page itself calls the API, which is the only real authority.
 */
export default async function ProtectedLayout({
  children,
}: LayoutProps<"/">) {
  const token = await getSessionToken();
  if (!token) redirect("/login");
  return <>{children}</>;
}
