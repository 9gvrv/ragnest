import type { ButtonHTMLAttributes } from "react";

export function Button({
  children,
  pending,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { pending?: boolean }) {
  return (
    <button
      className={[
        "inline-flex h-9 items-center justify-center rounded-md bg-foreground px-4 text-sm font-medium text-background transition-colors duration-150 hover:bg-foreground/90 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      disabled={pending || props.disabled}
      {...props}
    >
      {pending ? "Working…" : children}
    </button>
  );
}
