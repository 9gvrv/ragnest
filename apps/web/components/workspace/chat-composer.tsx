"use client";

import {
  useEffect,
  useId,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
} from "react";
import { ArrowUpIcon, StopIcon } from "@/components/workspace/icons";

type ChatComposerProps = {
  workspaceName: string;
  hasDocuments: boolean;
  streaming: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  onSubmitQuestion: (question: string) => void;
  onStop: () => void;
  onUploadRequest: () => void;
};

export function ChatComposer({
  workspaceName,
  hasDocuments,
  streaming,
  inputRef,
  onSubmitQuestion,
  onStop,
  onUploadRequest,
}: ChatComposerProps) {
  const [value, setValue] = useState("");
  const id = useId();
  const hintId = `${id}-hint`;
  const disabled = !hasDocuments;
  const canSend = !disabled && !streaming && value.trim().length > 0;

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
    setValue("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSend) {
        onSubmitQuestion(value.trim());
        setValue("");
      }
    }
  }

  return (
    <div>
      <form
        onSubmit={submit}
        className={[
          "rounded-xl border bg-surface transition-colors duration-150",
          disabled
            ? "border-border/70 bg-surface/60"
            : "border-border focus-within:border-accent/60",
        ].join(" ")}
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
          disabled={disabled || streaming}
          placeholder={
            disabled
              ? "Upload a document to start asking questions"
              : streaming
                ? "Waiting for the answer…"
                : "Ask a question about your documents"
          }
          aria-describedby={hintId}
          className="block max-h-[200px] min-h-16 w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-base leading-6 text-foreground placeholder:text-muted/70 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
        />

        <div className="flex items-center justify-between gap-3 px-3 pb-3">
          <p id={hintId} className="text-xs leading-5 text-muted">
            {disabled
              ? "Chat is locked until a document is ready."
              : streaming
                ? "Answering from this workspace's documents."
                : "Answers cite the documents in this workspace."}
          </p>
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop answer"
              className="grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-elevated text-foreground transition-colors duration-150 hover:border-control"
            >
              <StopIcon className="size-4" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Send question"
              className="grid size-9 shrink-0 place-items-center rounded-lg bg-foreground text-background transition-colors duration-150 hover:bg-foreground/90 disabled:cursor-not-allowed disabled:bg-foreground/10 disabled:text-muted"
            >
              <ArrowUpIcon className="size-4" />
            </button>
          )}
        </div>
      </form>

      {disabled ? (
        <div className="mt-3 flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1 text-center text-xs leading-5 text-muted">
          <span>Upload a document to unlock the chat.</span>
          <button
            type="button"
            onClick={onUploadRequest}
            className="font-medium text-accent underline-offset-4 transition-colors duration-150 hover:underline"
          >
            Upload a document
          </button>
        </div>
      ) : null}
    </div>
  );
}
