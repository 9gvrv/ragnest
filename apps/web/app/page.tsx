export default function Page() {
  return (
    <main className="mx-auto w-full max-w-[34rem] px-6 pt-[18vh] pb-24">
      <p className="text-[13px] font-medium tracking-[0.08em] text-action">
        Ragnest
      </p>

      <h1 className="mt-6 font-serif text-[clamp(2.25rem,5vw,3rem)] leading-[1.1] tracking-[-0.02em]">
        Ask your documents.
      </h1>

      <p className="mt-5 max-w-[60ch] font-serif text-[17px] leading-[1.65] text-muted">
        Answers drawn only from what you have uploaded, with the page each one
        came from.
      </p>

      <blockquote className="mt-10 border-l border-rule pl-5">
        <p className="max-w-[60ch] font-serif text-[17px] leading-[1.65]">
          <mark className="retrieved-mark bg-transparent">
            30 days from the invoice date.
          </mark>
        </p>
        <p className="mt-2 text-[13px] text-muted">
          refund-policy.pdf, page 3
        </p>
      </blockquote>

      <div className="mt-12 space-y-6">
        <div>
          <label className="block text-[13px] font-medium text-ink">
            Email
          </label>
          <input
            type="email"
            className="mt-2 w-full border-0 border-b border-rule bg-transparent py-2 text-[15px] placeholder:text-muted/60"
            placeholder="you@example.com"
          />
        </div>

        <button
          type="button"
          className="rounded-[3px] bg-action px-5 py-3 text-[15px] font-medium text-paper"
        >
          Sign in
        </button>
      </div>

      <div className="mt-10 flex gap-3">
        {[
          ["paper", "#f8f6f1"],
          ["ink", "#171a2b"],
          ["muted", "#5b5f73"],
          ["action", "#2b3a8f"],
          ["saffron", "#f5c445"],
          ["rule", "#ddd9ce"],
        ].map(([name, hex]) => (
          <div key={name} className="text-[12px] text-muted">
            <div
              className="mb-1 h-8 w-14 rounded-[2px] border border-rule"
              style={{ background: hex }}
            />
            {name}
          </div>
        ))}
      </div>
    </main>
  );
}
