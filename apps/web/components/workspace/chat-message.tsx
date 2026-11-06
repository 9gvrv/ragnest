"use client";

import { useId, useRef, useState, type RefObject } from "react";
import type { ApiCitation } from "@/lib/api";

export type ChatUiMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: ApiCitation[];
  finishReason: string | null;
  streaming: boolean;
};

/** Matches the ASCII `[1]` marker and Groq's full-width `【1】` variant. */
const MARKER = /(\[\d+\]|【\d+】)/g;
const MARKER_EXACT = /^(?:\[(\d+)\]|【(\d+)】)$/;

function markerNumber(part: string) {
  const match = MARKER_EXACT.exec(part);
  if (!match) return null;
  return Number(match[1] ?? match[2]);
}

function CitationMarker({
  n,
  active,
  onClick,
}: {
  n: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Show source ${n}`}
      aria-pressed={active}
      className={[
        "mx-0.5 inline-flex -translate-y-px items-baseline rounded border px-1 align-baseline font-mono text-[11px] leading-4 transition-colors duration-150",
        active
          ? "border-accent bg-accent/10 text-foreground"
          : "border-border bg-elevated text-accent hover:border-accent/60",
      ].join(" ")}
    >
      [{n}]
    </button>
  );
}

function SourceCards({
  id,
  citations,
  active,
  refs,
}: {
  id: string;
  citations: ApiCitation[];
  active: number | null;
  refs: RefObject<Record<number, HTMLLIElement | null>>;
}) {
  return (
    <ul aria-label="Sources" className="mt-3 space-y-2">
      {citations.map((citation) => (
        <li
          key={citation.chunk_id}
          id={`${id}-source-${citation.n}`}
          ref={(element) => {
            refs.current[citation.n] = element;
          }}
          className={[
            "rounded-lg border px-3 py-2 transition-colors duration-150",
            active === citation.n
              ? "border-accent/60 bg-accent/5"
              : "border-border bg-surface",
          ].join(" ")}
        >
          <div className="flex items-baseline gap-2">
            <span className="shrink-0 rounded border border-border bg-elevated px-1 font-mono text-[11px] leading-4 text-accent">
              {citation.n}
            </span>
            <span className="min-w-0 flex-1 truncate text-xs font-medium text-foreground">
              {citation.filename}
            </span>
            <span
              title="Cosine similarity"
              className="shrink-0 font-mono text-[11px] tabular-nums text-muted"
            >
              {citation.score > 0 ? `${Math.round(citation.score * 100)}%` : ""}
            </span>
          </div>
          <p className="mt-1 line-clamp-3 text-xs leading-5 text-muted">
            {citation.excerpt}
          </p>
        </li>
      ))}
    </ul>
  );
}

export function ChatMessage({ message }: { message: ChatUiMessage }) {
  const id = useId();
  const [active, setActive] = useState<number | null>(null);
  const refs = useRef<Record<number, HTMLLIElement | null>>({});

  function showSource(n: number) {
    const next = active === n ? null : n;
    setActive(next);
    if (next !== null) {
      const element = refs.current[next];
      element?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  if (message.role === "user") {
    return (
      <li className="ml-auto max-w-[85%] rounded-xl border border-border bg-surface px-4 py-3">
        <p className="text-xs text-muted">You</p>
        <p className="mt-1 text-sm leading-6 whitespace-pre-wrap text-foreground">
          {message.content}
        </p>
      </li>
    );
  }

  const hasCitations = message.citations.length > 0;
  const parts = message.content.split(MARKER);

  return (
    <li className="max-w-[85%]">
      <p className="text-xs text-muted">Ragnest</p>

      {message.streaming && message.content.length === 0 ? (
        <ThinkingDots />
      ) : (
        <p className="mt-1 text-sm leading-6 whitespace-pre-wrap text-foreground">
          {parts.map((part, index) => {
            const n = markerNumber(part);
            const cited = n !== null && hasCitations
              ? message.citations.some((citation) => citation.n === n)
              : false;

            if (n !== null && cited) {
              return (
                <CitationMarker
                  key={`${part}-${index}`}
                  n={n}
                  active={active === n}
                  onClick={() => showSource(n)}
                />
              );
            }
            return <span key={`${part}-${index}`}>{part}</span>;
          })}
        </p>
      )}

      {message.finishReason === "no_context" ? (
        <p className="mt-2 text-xs text-muted">
          No matching passages in this workspace.
        </p>
      ) : null}

      {message.finishReason === "cancelled" ? (
        <p className="mt-1 text-xs text-muted">Stopped.</p>
      ) : null}

      {hasCitations ? (
        <SourceCards id={id} citations={message.citations} active={active} refs={refs} />
      ) : null}
    </li>
  );
}

function ThinkingDots() {
  return (
    <span
      className="mt-2 flex items-center gap-1"
      aria-label="Ragnest is answering"
    >
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="size-1.5 animate-pulse rounded-full bg-muted motion-reduce:animate-none"
          style={{ animationDelay: `${index * 150}ms` }}
        />
      ))}
    </span>
  );
}
