/**
 * Placeholders for the marketing pages. Swap these for real values later —
 * every page reads from here, so the change happens in one place.
 */
export const site = {
  name: "Ragnest",
  /** Static pages prerender, so the year is set here rather than read from a clock. */
  year: 2026,
  /** Cover screenshot served from public/, sourced from screenshots/ragnest.png. */
  previewImage: "/app-preview.png",
  social: [{ label: "GitHub", href: "https://github.com/9gvrv/ragnest" }],
} as const;
