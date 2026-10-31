import type { ReactNode } from "react";
import { SiteShell } from "@/components/site-shell";

/**
 * The frame every auth screen sits in: the same dark chrome as the landing
 * page, then one quiet column with the headline, a line of orientation, and
 * the form.
 */
export function AuthShell({
  title,
  intro,
  children,
  footer,
}: {
  title: string;
  intro: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <SiteShell>
      <main className="mx-auto flex w-full max-w-[380px] flex-1 flex-col justify-center px-6 py-16 sm:py-24">
        <h1 className="text-[clamp(1.875rem,5vw,2.5rem)] leading-[1.1] font-semibold tracking-[-0.035em] text-balance">
          {title}
        </h1>
        <p className="mt-4 text-[15px] leading-6 text-pretty text-muted">
          {intro}
        </p>

        <div className="mt-10">{children}</div>

        {footer ? (
          <div className="mt-8 border-t border-border pt-6">{footer}</div>
        ) : null}
      </main>
    </SiteShell>
  );
}
