"use client";

import Link from "next/link";
import { SignOut } from "@/components/sign-out";
import { Menu } from "@/components/workspace/menu";
import { MoreHorizontalIcon } from "@/components/workspace/icons";
import type { ApiUser } from "@/lib/api";
import { initialsFromEmail } from "@/lib/workspace";

const itemClass =
  "flex w-full items-center rounded-md px-2.5 py-2 text-left text-sm text-muted transition-colors duration-150 hover:bg-surface hover:text-foreground";

export function UserMenu({ me }: { me: ApiUser }) {
  return (
    <Menu
      label="Account menu"
      side="top"
      triggerClassName="flex w-full items-center gap-2 rounded-md px-1 py-1.5 text-left transition-colors duration-150 hover:bg-surface"
      trigger={
        <>
          <span
            aria-hidden="true"
            className="grid size-7 shrink-0 place-items-center rounded-full border border-border bg-elevated text-xs font-semibold text-muted"
          >
            {initialsFromEmail(me.email)}
          </span>
          <span className="min-w-0 flex-1 truncate text-sm text-foreground">
            {me.email}
          </span>
          <MoreHorizontalIcon className="size-4 shrink-0 text-muted" />
        </>
      }
    >
      <Link href="/account" className={itemClass}>
        Your account
      </Link>
      <SignOut className={itemClass} />
    </Menu>
  );
}
