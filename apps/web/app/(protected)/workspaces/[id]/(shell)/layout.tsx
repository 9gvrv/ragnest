import type { ReactNode } from "react";

/**
 * The app-shell wrapper for the workspace page only. It lives in a route group
 * so the document detail page, which shares the /workspaces/[id] segment, does
 * not inherit the fixed-height shell.
 */
export default function WorkspaceAppShellLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="dark-surface h-dvh overflow-hidden">{children}</div>
  );
}
