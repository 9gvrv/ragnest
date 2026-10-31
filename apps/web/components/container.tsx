import type { ReactNode } from "react";

/**
 * The page grid for the marketing site: 1280px at its widest, with 24px gutters
 * on small screens and 32px from `lg` up. Navbar, hero, preview, and footer all
 * use it so their edges line up.
 */
export function Container({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={[
        "mx-auto w-full max-w-7xl px-6 lg:px-8",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}
