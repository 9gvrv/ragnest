/**
 * The mark is two nested squares — a literal nest, and a reminder that every
 * answer stays inside the workspace it came from. It sits on a light tile so
 * it holds up on the dark chrome.
 */
export function LogoMark() {
  return (
    <span
      aria-hidden="true"
      className="grid size-[22px] shrink-0 place-items-center rounded-[6px] bg-foreground text-background"
    >
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <rect
          x="2.1"
          y="2.1"
          width="7.8"
          height="7.8"
          rx="1.7"
          stroke="currentColor"
          strokeWidth="1.3"
        />
        <rect x="4.8" y="4.8" width="4.2" height="4.2" rx="1" fill="currentColor" />
      </svg>
    </span>
  );
}
