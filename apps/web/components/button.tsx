import type { ButtonHTMLAttributes } from "react";

export function Button({
  children,
  pending,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { pending?: boolean }) {
  return (
    <button
      className="rounded-[3px] bg-action px-5 py-3 text-[15px] font-medium text-paper transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      disabled={pending || props.disabled}
      {...props}
    >
      {pending ? "Working…" : children}
    </button>
  );
}
