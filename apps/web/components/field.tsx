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
      <label htmlFor={fieldId} className="block text-[13px] font-medium">
        {label}
      </label>
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className="mt-2 w-full border-0 border-b border-rule bg-transparent py-2 text-[15px] outline-none focus:border-action aria-[invalid=true]:border-[#a3341f]"
        {...props}
      />
      {error ? (
        <p id={`${fieldId}-error`} className="mt-2 text-[13px] text-[#a3341f]">
          {error}
        </p>
      ) : hint ? (
        <p id={`${fieldId}-hint`} className="mt-2 text-[13px] text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
