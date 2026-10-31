/**
 * Placeholders for the marketing pages. Swap these for real values later —
 * every page reads from here, so the change happens in one place.
 */
export const site = {
  name: "Ragnest",
  author: "Gaurav",
  /** Static pages prerender, so the year is set here rather than read from a clock. */
  year: 2026,
  /** Replace public/app-preview.png with a real screenshot at the same path. */
  previewImage: "/app-preview.png",
  social: [
    { label: "GitHub", href: "https://github.com/9gvrv" },
    { label: "LinkedIn", href: "https://www.linkedin.com/in/gaurav111/" },
    { label: "X", href: "https://x.com/slopsoap" },
  ],
} as const;
