import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Container } from "@/components/container";
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
        <Container className="pt-24 pb-16 sm:pt-32 sm:pb-20 lg:pt-36">
          <h1 className="max-w-4xl text-[clamp(2.25rem,6vw,5rem)] leading-[1.02] font-semibold tracking-[-0.045em] text-balance">
            The knowledge system for teams and agents
          </h1>

          <p className="mt-6 max-w-[42rem] text-[17px] leading-7 text-pretty text-muted sm:text-lg">
            Upload documents, ask questions, get answers with citations. Built
            for the AI era.
          </p>

          <div className="mt-9">
            <Link
              href="/signup"
              className="inline-flex h-11 items-center justify-center rounded-full bg-foreground px-6 text-[15px] font-medium text-background transition-colors duration-150 hover:bg-foreground/90"
            >
              Create an account
            </Link>
          </div>
        </Container>

        <section aria-label="Product preview" className="pb-24 sm:pb-32">
          <Container>
            <div className="relative">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -inset-x-10 -top-20 bottom-0 rounded-full bg-[radial-gradient(50%_50%_at_50%_50%,rgba(124,156,255,0.14),transparent_70%)] blur-3xl"
              />

              <div className="relative overflow-hidden rounded-xl border border-border bg-surface p-1.5 shadow-[0_40px_120px_-48px_rgba(0,0,0,0.9)]">
                <div className="relative overflow-hidden rounded-[7px]">
                  <Image
                    src={site.previewImage}
                    alt="A Ragnest workspace showing an answer with citations to the source document and page."
                    width={1600}
                    height={1000}
                    priority
                    sizes="(min-width: 1280px) 1216px, (min-width: 1024px) calc(100vw - 64px), calc(100vw - 48px)"
                    className="h-auto w-full"
                  />
                  <div
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-background via-background/70 to-transparent"
                  />
                </div>
              </div>
            </div>
          </Container>
        </section>
      </main>
    </SiteShell>
  );
}
