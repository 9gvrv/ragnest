import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { SiteShell } from "@/components/site-shell";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Ragnest — The knowledge system for teams and agents",
  description:
    "Upload documents, ask questions, get answers with citations. Built for the AI era.",
};

export default function LandingPage() {
  return (
    <SiteShell>
      <main className="flex-1">
        <section className="mx-auto w-full max-w-6xl px-6 pt-20 pb-14 text-center sm:pt-28 sm:pb-20">
          <h1 className="mx-auto max-w-3xl text-[clamp(1.875rem,6.5vw,4.5rem)] leading-[1.04] font-semibold tracking-[-0.04em] text-balance">
            The knowledge system{" "}
            <span className="sm:block">for teams and agents</span>
          </h1>

          <p className="mx-auto mt-6 max-w-[38rem] text-[17px] leading-7 text-pretty text-muted">
            Upload documents, ask questions, get answers with citations.{" "}
            <span className="sm:block">Built for the AI era.</span>
          </p>

          <div className="mt-9 flex items-center justify-center">
            <Link
              href="/signup"
              className="inline-flex h-10 items-center justify-center rounded-full bg-foreground px-5 text-sm font-medium text-background transition-colors duration-150 hover:bg-foreground/90"
            >
              Create an account
            </Link>
          </div>
        </section>

        <section
          aria-label="Product preview"
          className="mx-auto w-full max-w-5xl px-6 pb-24 sm:pb-32"
        >
          <div className="relative">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-x-8 -top-16 bottom-8 rounded-full bg-[radial-gradient(50%_50%_at_50%_50%,rgba(124,156,255,0.16),transparent_70%)] blur-2xl"
            />
            <div className="relative overflow-hidden rounded-xl border border-border bg-surface p-1.5 shadow-[0_40px_120px_-48px_rgba(0,0,0,0.9)]">
              <Image
                src={site.previewImage}
                alt="A Ragnest workspace showing an answer with citations to the source document and page."
                width={1600}
                height={1000}
                priority
                sizes="(min-width: 1024px) 960px, 100vw"
                className="h-auto w-full rounded-[7px] border border-border/60"
              />
            </div>
          </div>
        </section>
      </main>
    </SiteShell>
  );
}
