import type { ReactNode } from "react";
import { SiteFooter } from "@/components/site-footer";
import { SiteNav } from "@/components/site-nav";

/**
 * The dark frame shared by the landing and auth pages. The `dark-surface`
 * class scopes the dark tokens; nothing outside this subtree changes.
 */
export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="dark-surface flex min-h-svh flex-1 flex-col">
      <SiteNav />
      {children}
      <SiteFooter />
    </div>
  );
}
