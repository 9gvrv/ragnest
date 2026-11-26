import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Container } from "@/components/container";
import { SiteShell } from "@/components/site-shell";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Ragnest — Ask your documents, get answers you can check",
  description:
    "Turn your team's txt, md, and pdf files into a knowledge base you can question in plain language. Every answer cites the document it came from.",
};

const facts = [
  {
    label: "Answers with sources",
    detail: "Every reply points back to the document it came from.",
  },
  {
    label: "Only your workspace",
    detail: "Documents and chats stay inside the workspace they belong to.",
  },
  {
    label: "Files you already have",
    detail: "Upload txt, md, or pdf files up to 5 MB each.",
  },
];

const steps = [
  {
    title: "Create a workspace",
    detail:
      "One private place for a team, a project, or a topic. Invite people only when you want to share.",
  },
  {
    title: "Add your documents",
    detail:
      "Drop in txt, md, and pdf files. Ragnest reads the text and indexes it in the background.",
  },
  {
    title: "Ask a question",
    detail:
      "Chat the way you would with a colleague. Answers come from that workspace's documents and cite the source.",
  },
];

const guarantees = [
  {
    title: "Grounded in your files",
    detail:
      "Ragnest finds relevant passages in your workspace before it writes an answer. It does not fill gaps from general knowledge.",
  },
  {
    title: "Honest when it does not know",
    detail:
      "If no document covers the question, you get a clear refusal instead of a confident guess.",
  },
  {
    title: "Citations that stick",
    detail:
      "Each answer saves its source snapshot, so you can still see where it came from later.",
  },
];

const primaryLink =
  "inline-flex h-11 items-center justify-center rounded-full bg-foreground px-6 text-sm font-medium text-background transition-colors duration-150 hover:bg-foreground/90";
const secondaryLink =
  "inline-flex h-11 items-center justify-center rounded-full border border-border px-6 text-sm font-medium text-foreground transition-colors duration-150 hover:border-muted";

export default function LandingPage() {
  return (
    <SiteShell>
      <main className="flex-1">
        <Container className="pt-20 pb-12 sm:pt-28 sm:pb-16">
          <div className="max-w-3xl">
            <h1 className="text-[clamp(2.5rem,5vw,3rem)] leading-[1.08] font-semibold tracking-[-0.04em] text-balance">
              Ask your documents. Get answers you can check.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
              Ragnest turns the files your team already has into a knowledge base
              you can question in plain language. Every answer comes from your
              workspace&apos;s documents and cites the file it came from, so you
              can verify it in seconds.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className={primaryLink}>
                Create an account
              </Link>
              <Link href="#how-it-works" className={secondaryLink}>
                See how it works
              </Link>
            </div>
          </div>
        </Container>

        <section aria-label="What Ragnest gives you" className="border-y border-border">
          <Container className="grid gap-8 py-8 sm:grid-cols-3">
            {facts.map((fact) => (
              <div key={fact.label}>
                <h2 className="text-sm font-medium">{fact.label}</h2>
                <p className="mt-2 max-w-xs text-sm leading-6 text-muted">
                  {fact.detail}
                </p>
              </div>
            ))}
          </Container>
        </section>

        <section aria-label="Product preview" className="py-14 sm:py-20">
          <Container>
            <figure>
              <div className="overflow-hidden rounded-lg border border-border bg-surface">
                <Image
                  src={site.previewImage}
                  alt="A Ragnest workspace with documents and chats in the sidebar and a new chat ready in the main pane."
                  width={1907}
                  height={932}
                  priority
                  sizes="(min-width: 1280px) 1216px, (min-width: 1024px) calc(100vw - 64px), calc(100vw - 48px)"
                  className="h-auto w-full"
                />
              </div>
              <figcaption className="mt-4 text-[13px] text-muted">
                A Ragnest workspace: documents, members, and chats in one place.
              </figcaption>
            </figure>
          </Container>
        </section>

        <section
          id="how-it-works"
          aria-labelledby="how-it-works-heading"
          className="border-t border-border py-14 sm:py-20"
        >
          <Container>
            <h2
              id="how-it-works-heading"
              className="text-2xl font-semibold tracking-[-0.03em] text-balance sm:text-3xl"
            >
              From files to answers in three steps
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
              You don&apos;t need to configure a vector store or write prompts.
              Ragnest handles the indexing, so you can spend your time on the
              question instead of the setup.
            </p>
            <ol className="mt-10 grid gap-8 sm:grid-cols-3 sm:gap-10">
              {steps.map((step, index) => (
                <li key={step.title} className="border-t border-border pt-5">
                  <span className="font-mono text-[13px] text-muted">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-3 text-lg font-medium tracking-[-0.02em]">
                    {step.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {step.detail}
                  </p>
                </li>
              ))}
            </ol>
          </Container>
        </section>

        <section
          aria-labelledby="grounded-heading"
          className="border-t border-border py-14 sm:py-20"
        >
          <Container>
            <h2
              id="grounded-heading"
              className="text-2xl font-semibold tracking-[-0.03em] text-balance sm:text-3xl"
            >
              Know where every answer came from
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
              General-purpose chat tools will answer about anything, whether or
              not they have the facts. Ragnest answers only from the documents in
              the workspace you asked, and shows you the source alongside the
              answer.
            </p>
            <dl className="mt-10 grid gap-8 sm:grid-cols-3 sm:gap-10">
              {guarantees.map((guarantee) => (
                <div key={guarantee.title} className="border-t border-border pt-5">
                  <dt className="text-[15px] font-medium">{guarantee.title}</dt>
                  <dd className="mt-2 text-sm leading-6 text-muted">
                    {guarantee.detail}
                  </dd>
                </div>
              ))}
            </dl>
          </Container>
        </section>

        <section className="border-t border-border py-14 sm:py-20">
          <Container className="flex flex-col items-start gap-6 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-[-0.03em] text-balance sm:text-3xl">
                Start with one document
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-6 text-muted">
                Create a workspace, add a file, and ask your first question. Your
                answers will always point back to the source.
              </p>
            </div>
            <Link href="/signup" className={primaryLink}>
              Create an account
            </Link>
          </Container>
        </section>
      </main>
    </SiteShell>
  );
}
