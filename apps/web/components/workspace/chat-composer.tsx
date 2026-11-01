"use client";

import {
  useEffect,
  useId,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
} from "react";
import { ArrowUpIcon } from "@/components/workspace/icons";

type ChatComposerProps = {
  workspaceName: string;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  onSubmitQuestion: (question: string) => void;
};

export function ChatComposer({
  workspaceName,
  inputRef,
  onSubmitQuestion,
}: ChatComposerProps) {
  const [value, setValue] = useState("");
  const id = useId();
  const hintId = `${id}-hint`;
  const canSend = value.trim().length > 0;

  useEffect(() => {
    const element = inputRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  }, [inputRef, value]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSend) return;
    onSubmitQuestion(value.trim());
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSend) onSubmitQuestion(value.trim());
    }
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-border bg-surface transition-colors duration-150 focus-within:border-accent/60"
    >
      <label htmlFor={id} className="sr-only">
        Ask about {workspaceName}
      </label>
      <textarea
        id={id}
        ref={inputRef}
        rows={1}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask a question about your documents"
        aria-describedby={hintId}
        className="block max-h-[200px] min-h-14 w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-base leading-6 text-foreground placeholder:text-muted/70 focus-visible:outline-none"
      />

      <div className="flex items-center justify-between gap-3 px-3 pb-3">
        <p id={hintId} className="text-xs leading-5 text-muted">
          Answers cite the documents in this workspace.
        </p>
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send question"
          className="grid size-9 shrink-0 place-items-center rounded-lg bg-foreground text-background transition-colors duration-150 hover:bg-foreground/90 disabled:cursor-not-allowed disabled:bg-foreground/10 disabled:text-muted"
        >
          <ArrowUpIcon className="size-4" />
        </button>
      </div>
    </form>
  );
}
