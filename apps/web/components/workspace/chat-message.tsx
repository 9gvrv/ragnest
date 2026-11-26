"use client";

import { useEffect, useId, useRef, useState, type RefObject } from "react";
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

/** Keep the collapsed grid scannable; the rest sits behind one small button. */
const PREVIEW_COUNT = 4;

function markerNumber(part: string) {
  const match = MARKER_EXACT.exec(part);
  if (!match) return null;
  return Number(match[1] ?? match[2]);
}

function truncate(text: string, max: number) {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const boundary = cut.lastIndexOf(" ");
  const end = boundary > max / 2 ? cut.slice(0, boundary) : cut;
  return `${end.trimEnd()}…`;
}

/**
 * A chunk has no title field of its own. Its first non-empty line is usually a
 * heading or the opening sentence, which reads much better on a collapsed tile
 * than a filename alone. Fall back to the filename when that line is empty.
 */
function sourceTitle(citation: ApiCitation) {
  const line = citation.excerpt
    .split("\n")
    .map((part) => part.trim())
    .find((part) => part.length > 0);
  if (!line) return citation.filename;

  const title = line
    .replace(/^#{1,6}\s+/, "")
    .replace(/^[-*>]\s+/, "")
    .replace(/^\d+[.)]\s+/, "")
    .replace(/[`*]/g, "")
    .trim();

  return title.length > 0 ? truncate(title, 64) : citation.filename;
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

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 12 12"
      className={`size-3 shrink-0 transition-transform duration-150 ${
        open ? "rotate-180" : ""
      }`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m3 4.5 3 3 3-3" />
    </svg>
  );
}

function Sources({
  id,
  citations,
  active,
  open,
  showAll,
  refs,
  onToggleOpen,
  onToggleShowAll,
  onSelectFromCard,
}: {
  id: string;
  citations: ApiCitation[];
  active: number | null;
  open: boolean;
  showAll: boolean;
  refs: RefObject<Record<number, HTMLLIElement | null>>;
  onToggleOpen: () => void;
  onToggleShowAll: () => void;
  onSelectFromCard: (n: number) => void;
}) {
  const visible = showAll ? citations : citations.slice(0, PREVIEW_COUNT);

  return (
    <section aria-label="Sources" className="mt-3">
      <button
        type="button"
        onClick={onToggleOpen}
        aria-expanded={open}
        aria-controls={`${id}-sources`}
        className="mb-2 inline-flex items-center gap-1.5 text-xs font-medium text-muted transition-colors duration-150 hover:text-foreground"
      >
        <Chevron open={open} />
        Sources
        <span className="rounded border border-border bg-elevated px-1 font-mono text-[11px] leading-4 text-muted">
          {citations.length}
        </span>
      </button>

      {open ? (
        <>
          <ul
            id={`${id}-sources`}
            className="grid grid-cols-1 gap-2 sm:grid-cols-2"
          >
            {visible.map((citation) => {
              const expanded = active === citation.n;
              return (
                <li
                  key={citation.chunk_id}
                  id={`${id}-source-${citation.n}`}
                  ref={(element) => {
                    refs.current[citation.n] = element;
                  }}
                  className={[
                    "min-w-0 self-start rounded-lg border transition-colors duration-150",
                    expanded
                      ? "col-span-full border-accent/60 bg-accent/5"
                      : "border-border bg-surface hover:border-accent/40",
                  ].join(" ")}
                >
                  <button
                    type="button"
                    onClick={() => onSelectFromCard(citation.n)}
                    aria-expanded={expanded}
                    aria-controls={`${id}-source-${citation.n}-detail`}
                    className="block w-full px-3 py-2 text-left"
                  >
                    <span className="flex items-baseline gap-2">
                      <span className="shrink-0 rounded border border-border bg-elevated px-1 font-mono text-[11px] leading-4 text-accent">
                        {citation.n}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-[11px] text-muted">
                        {citation.filename} · chunk {citation.chunk_index + 1}
                      </span>
                      {citation.score > 0 ? (
                        <span
                          title="Cosine similarity"
                          className="shrink-0 font-mono text-[11px] tabular-nums text-muted"
                        >
                          {Math.round(citation.score * 100)}%
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-1 block line-clamp-2 text-xs font-medium leading-5 text-foreground">
                      {sourceTitle(citation)}
                    </span>
                  </button>
                  {expanded ? (
                    <div
                      id={`${id}-source-${citation.n}-detail`}
                      className="border-t border-border px-3 py-2"
                    >
                      <p className="whitespace-pre-wrap text-xs leading-5 text-muted">
                        {citation.excerpt}
                      </p>
                      <p className="mt-2 font-mono text-[11px] text-muted">
                        chars {citation.char_start}–{citation.char_end}
                      </p>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>

          {citations.length > PREVIEW_COUNT ? (
            <button
              type="button"
              onClick={onToggleShowAll}
              className="mt-2 text-xs text-accent transition-colors duration-150 hover:underline"
            >
              {showAll
                ? "Show fewer"
                : `Show ${citations.length - PREVIEW_COUNT} more`}
            </button>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

export function ChatMessage({ message }: { message: ChatUiMessage }) {
  const id = useId();
  const [active, setActive] = useState<number | null>(null);
  const [open, setOpen] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const refs = useRef<Record<number, HTMLLIElement | null>>({});

  // A marker can open a source that was hidden by the preview limit, so wait
  // for the state above to render before scrolling to it.
  useEffect(() => {
    if (active === null) return;
    refs.current[active]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [active, open, showAll]);

  function selectFromCard(n: number) {
    setActive((current) => (current === n ? null : n));
  }

  function selectFromMarker(n: number) {
    setOpen(true);
    setShowAll(true);
    setActive((current) => (current === n ? null : n));
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
                  onClick={() => selectFromMarker(n)}
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
        <Sources
          id={id}
          citations={message.citations}
          active={active}
          open={open}
          showAll={showAll}
          refs={refs}
          onToggleOpen={() => setOpen((current) => !current)}
          onToggleShowAll={() => setShowAll((current) => !current)}
          onSelectFromCard={selectFromCard}
        />
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
