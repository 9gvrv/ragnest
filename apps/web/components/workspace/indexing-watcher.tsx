"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

const TICK_MS = 2500;
const MAX_TICKS = 40;

/**
 * While any document is still being indexed, ask the server for fresh status
 * every couple of seconds. Paused while the tab is hidden; gives up after
 * about 100 seconds so a stuck job cannot poll forever.
 */
export function IndexingWatcher({ active }: { active: boolean }) {
  const router = useRouter();

  useEffect(() => {
    if (!active) return;

    let ticks = 0;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      ticks += 1;
      if (ticks > MAX_TICKS) {
        window.clearInterval(timer);
        return;
      }
      router.refresh();
    }, TICK_MS);

    return () => window.clearInterval(timer);
  }, [active, router]);

  return null;
}
