/**
 * The one scrollbar treatment for the sidebar's scroll areas: a thin,
 * low-contrast thumb that only shows while the area is hovered, plus a stable
 * gutter so the content width never jumps when the scrollbar appears.
 *
 * WebKit/Blink use the legacy pseudo-elements (no arrow buttons). Firefox gets
 * the standard properties behind an `@supports` guard, because setting them in
 * Chromium would disable the pseudo-element styling.
 */
export const sidebarScroll = [
  "min-h-0 overflow-y-auto overscroll-contain",
  "[scrollbar-gutter:stable]",
  "supports-[-moz-appearance:none]:[scrollbar-width:thin]",
  "supports-[-moz-appearance:none]:[scrollbar-color:transparent_transparent]",
  "supports-[-moz-appearance:none]:hover:[scrollbar-color:var(--color-control)_transparent]",
  "[&::-webkit-scrollbar]:w-1.5",
  "[&::-webkit-scrollbar-button]:hidden",
  "[&::-webkit-scrollbar-track]:bg-transparent",
  "[&::-webkit-scrollbar-thumb]:rounded-full",
  "[&::-webkit-scrollbar-thumb]:bg-transparent",
  "[&:hover::-webkit-scrollbar-thumb]:bg-control",
].join(" ");
