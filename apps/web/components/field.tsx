import type { InputHTMLAttributes } from "react";

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
};

/**
 * A labelled input drawn as a single rule rather than a box, with the error
 * sitting where the hint would be so nothing jumps when it appears.
 */
export function Field({ label, hint, error, id, ...props }: FieldProps) {
  const fieldId = id ?? props.name;
  const describedBy = error
    ? `${fieldId}-error`
    : hint
      ? `${fieldId}-hint`
      : undefined;

  return (
    <div>
      <label
        htmlFor={fieldId}
        className="block text-sm font-medium text-foreground"
      >
        {label}
      </label>
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className="mt-2 block h-10 w-full rounded-md border border-control bg-background px-3 text-base text-foreground transition-colors duration-150 placeholder:text-muted/70 hover:border-foreground/60 focus:border-foreground aria-invalid:border-danger"
        {...props}
      />
      {error ? (
        <p id={`${fieldId}-error`} className="mt-2 text-sm text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={`${fieldId}-hint`} className="mt-2 text-sm text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
