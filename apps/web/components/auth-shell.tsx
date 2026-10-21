import type { ReactNode } from "react";

/**
 * The frame every auth screen sits in: wordmark, headline, one paragraph of
 * orientation, the retrieved-sentence motif, then whatever the screen needs.
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
    <main className="mx-auto flex w-full max-w-136 flex-1 flex-col px-6 pt-[14vh] pb-20">
      <header>
        <p className="text-[13px] font-medium tracking-[0.08em] text-action">
          Ragnest
        </p>
        <h1 className="mt-6 font-serif text-[clamp(2.25rem,5vw,3rem)] leading-[1.1] tracking-[-0.02em]">
          {title}
        </h1>
        <p className="mt-5 max-w-[60ch] font-serif text-[17px] leading-[1.65] text-muted">
          {intro}
        </p>
      </header>

      <RetrievedSentence />

      <div className="mt-10">{children}</div>

      {footer ? <div className="pt-12">{footer}</div> : null}
    </main>
  );
}

function RetrievedSentence() {
  return (
    <figure className="mt-9 border-l border-rule pl-5">
      <blockquote className="max-w-[60ch] font-serif text-[17px] leading-[1.65]">
        <mark className="retrieved-mark bg-transparent">
          30 days from the invoice date.
        </mark>
      </blockquote>
      <figcaption className="mt-2 text-[13px] text-muted">
        refund-policy.pdf, page 3
      </figcaption>
    </figure>
  );
}
