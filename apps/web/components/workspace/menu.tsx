"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";

type MenuProps = {
  label: string;
  trigger: ReactNode;
  triggerClassName?: string;
  side?: "top" | "bottom";
  align?: "start" | "end";
  children: ReactNode;
};

/**
 * A small popover of actions. It closes on Escape or a click outside, and moves
 * focus to the first action when it opens so it works from the keyboard.
 */
export function Menu({
  label,
  trigger,
  triggerClassName,
  side = "bottom",
  align = "start",
  children,
}: MenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    menuRef.current?.querySelector<HTMLElement>("a, button")?.focus();
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((value) => !value)}
        className={triggerClassName}
      >
        {trigger}
      </button>

      {open ? (
        <div
          ref={menuRef}
          id={id}
          role="group"
          aria-label={label}
          className={[
            "absolute z-50 min-w-44 rounded-lg border border-border bg-background p-1",
            side === "top" ? "bottom-full mb-1" : "top-full mt-1",
            align === "end" ? "right-0" : "left-0",
          ].join(" ")}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
